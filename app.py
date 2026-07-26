#!/usr/bin/env python3
"""Waitgains backend: business signup + Stripe Connect payout onboarding.

Businesses ("customers") sign up with their email and connect a Stripe account
(Stripe Connect Express, test/sandbox mode) so they can receive payouts of their
revenue share. This is the backend for the Waitgains landing page.

Environment variables:
    STRIPE_SECRET_KEY        Stripe secret key. Use a test key (``sk_test_...``)
                             for the sandbox. Required for the Stripe payout flow;
                             email signup works without it.
    STRIPE_PUBLISHABLE_KEY   Optional publishable key (``pk_test_...``), surfaced
                             to the frontend for future client-side use.
    PUBLIC_BASE_URL          Base URL used to build Stripe onboarding return/refresh
                             links, e.g. ``https://xxxx.trycloudflare.com``. Defaults
                             to the incoming request's host.
    FLASK_SECRET_KEY         Session signing key. A random one is generated if unset
                             (sessions won't survive a restart in that case).
    DATABASE_PATH            SQLite file path. Defaults to ``waitgains.db``.

Run (dev):
    python3 app.py            # http://localhost:8000
"""

from __future__ import annotations

import datetime as _dt
import os
import pathlib
import secrets
import sqlite3
from typing import Optional

from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

try:
    import stripe
except ImportError:  # pragma: no cover - dependency is declared in requirements
    stripe = None

ROOT = pathlib.Path(__file__).resolve().parent
README = ROOT / "README.md"
DB_PATH = os.environ.get("DATABASE_PATH", str(ROOT / "waitgains.db"))

# Waitgains' advertised revenue share to the business (see landing page).
BUSINESS_REVENUE_SHARE = 0.60

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()
if stripe is not None and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def stripe_enabled() -> bool:
    return stripe is not None and bool(STRIPE_SECRET_KEY)


# --------------------------------------------------------------------------- #
# Database helpers
# --------------------------------------------------------------------------- #
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            email             TEXT UNIQUE NOT NULL,
            stripe_account_id TEXT,
            payouts_enabled   INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def find_customer(email: str) -> Optional[sqlite3.Row]:
    return get_db().execute(
        "SELECT * FROM customers WHERE email = ?", (email.lower(),)
    ).fetchone()


def upsert_customer(email: str) -> sqlite3.Row:
    db = get_db()
    existing = find_customer(email)
    if existing is None:
        db.execute(
            "INSERT INTO customers (email, created_at) VALUES (?, ?)",
            (email.lower(), _dt.datetime.utcnow().isoformat()),
        )
        db.commit()
    return find_customer(email)


def set_stripe_account(email: str, account_id: str) -> None:
    db = get_db()
    db.execute(
        "UPDATE customers SET stripe_account_id = ? WHERE email = ?",
        (account_id, email.lower()),
    )
    db.commit()


def set_payouts_enabled(email: str, enabled: bool) -> None:
    db = get_db()
    db.execute(
        "UPDATE customers SET payouts_enabled = ? WHERE email = ?",
        (1 if enabled else 0, email.lower()),
    )
    db.commit()


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #
def base_url() -> str:
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.url_root.rstrip("/")


def landing_html() -> str:
    text = README.read_text(encoding="utf-8")
    idx = text.find("<!DOCTYPE")
    if idx == -1:
        idx = text.find("<html")
    return text[idx:] if idx != -1 else text


def refresh_account_status(email: str) -> Optional[dict]:
    """Fetch the latest Stripe account status and persist payouts_enabled."""
    customer = find_customer(email)
    if not customer or not customer["stripe_account_id"] or not stripe_enabled():
        return None
    account = stripe.Account.retrieve(customer["stripe_account_id"])
    set_payouts_enabled(email, bool(account.get("payouts_enabled")))
    return account


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return landing_html()


@app.route("/signup")
def signup_page():
    return render_template("signup.html")


@app.route("/dashboard")
def dashboard_page():
    email = session.get("email")
    if not email:
        return redirect(url_for("signup_page"))

    customer = find_customer(email)
    if customer is None:
        session.pop("email", None)
        return redirect(url_for("signup_page"))

    account = None
    requirements_due = []
    if customer["stripe_account_id"] and stripe_enabled():
        account = refresh_account_status(email)
        customer = find_customer(email)
        if account is not None:
            requirements_due = (account.get("requirements") or {}).get(
                "currently_due", []
            )

    return render_template(
        "dashboard.html",
        email=email,
        customer=customer,
        stripe_enabled=stripe_enabled(),
        account=account,
        requirements_due=requirements_due,
        revenue_share=int(BUSINESS_REVENUE_SHARE * 100),
    )


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.post("/api/signup")
def api_signup():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"ok": False, "error": "Please enter a valid email address."}), 400

    upsert_customer(email)
    session["email"] = email.lower()
    return jsonify({"ok": True, "email": email.lower(), "redirect": url_for("dashboard_page")})


@app.post("/api/connect/start")
def api_connect_start():
    email = session.get("email")
    if not email:
        return jsonify({"ok": False, "error": "Not signed in."}), 401
    if not stripe_enabled():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Stripe is not configured on the server. Set STRIPE_SECRET_KEY (test mode).",
                }
            ),
            503,
        )

    customer = find_customer(email)
    account_id = customer["stripe_account_id"]

    if not account_id:
        account = stripe.Account.create(
            type="express",
            email=email,
            capabilities={"transfers": {"requested": True}},
            business_type="individual",
            metadata={"waitgains_email": email},
        )
        account_id = account.id
        set_stripe_account(email, account_id)

    account_link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{base_url()}/connect/refresh",
        return_url=f"{base_url()}/connect/return",
        type="account_onboarding",
    )
    return jsonify({"ok": True, "url": account_link.url})


@app.get("/connect/refresh")
def connect_refresh():
    # Stripe hits this when an onboarding link expires; mint a fresh one.
    email = session.get("email")
    if not email or not stripe_enabled():
        return redirect(url_for("dashboard_page"))
    customer = find_customer(email)
    if not customer or not customer["stripe_account_id"]:
        return redirect(url_for("dashboard_page"))
    account_link = stripe.AccountLink.create(
        account=customer["stripe_account_id"],
        refresh_url=f"{base_url()}/connect/refresh",
        return_url=f"{base_url()}/connect/return",
        type="account_onboarding",
    )
    return redirect(account_link.url)


@app.get("/connect/return")
def connect_return():
    email = session.get("email")
    if email and stripe_enabled():
        refresh_account_status(email)
    return redirect(url_for("dashboard_page"))


@app.post("/api/simulate-earning")
def api_simulate_earning():
    """Demo the payout loop in test mode.

    Creates a test charge to fund the platform balance immediately, then
    transfers the business's revenue share to their connected account. This
    mirrors how Waitgains would pay out ad revenue.
    """
    email = session.get("email")
    if not email:
        return jsonify({"ok": False, "error": "Not signed in."}), 401
    if not stripe_enabled():
        return jsonify({"ok": False, "error": "Stripe is not configured."}), 503

    customer = find_customer(email)
    if not customer or not customer["stripe_account_id"]:
        return jsonify({"ok": False, "error": "Connect a Stripe account first."}), 400

    account = refresh_account_status(email)
    if not account or not account.get("payouts_enabled"):
        return (
            jsonify(
                {"ok": False, "error": "Finish Stripe onboarding before receiving payouts."}
            ),
            400,
        )

    gross_cents = 1000  # $10.00 of simulated ad revenue
    share_cents = int(gross_cents * BUSINESS_REVENUE_SHARE)

    # tok_bypassPending makes test-mode funds immediately available for transfer.
    stripe.Charge.create(
        amount=gross_cents,
        currency="usd",
        source="tok_bypassPending",
        description="Waitgains simulated ad revenue (test)",
    )
    transfer = stripe.Transfer.create(
        amount=share_cents,
        currency="usd",
        destination=customer["stripe_account_id"],
        description="Waitgains revenue share payout (test)",
    )
    return jsonify(
        {
            "ok": True,
            "gross": gross_cents / 100,
            "payout": share_cents / 100,
            "transfer_id": transfer.id,
        }
    )


@app.post("/api/logout")
def api_logout():
    session.pop("email", None)
    return jsonify({"ok": True})


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "stripe_enabled": stripe_enabled()})


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
