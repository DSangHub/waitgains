# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
Waitgains (waitgains.com) — a product that lets businesses monetize phone hold time
and earn a revenue share. The marketing landing page markup lives inside `README.md`
(prefixed with a `# waitgains` markdown heading, followed by a full `<!DOCTYPE html>`
document). `app.py` is a Flask backend that serves that landing page plus the
business signup + Stripe payout flow.

### Running the app (dev)
```
pip install --break-system-packages -r requirements.txt   # deps (see update script)
PORT=8000 python3 app.py                                   # http://localhost:8000
```

Routes: `/` (landing page), `/signup`, `/dashboard`, `POST /api/signup`,
`POST /api/connect/start` (Stripe onboarding link), `/connect/return`,
`/connect/refresh`, `POST /api/simulate-earning` (test payout), `GET /healthz`.
Customer data is stored in a local SQLite file (`waitgains.db`, gitignored).

### Environment variables (see top of `app.py` for the full list)
- `STRIPE_SECRET_KEY` — Stripe **test** secret key (`sk_test_...`). Required for the
  payout flow; email signup works without it. `/healthz` reports `stripe_enabled`.
- `PUBLIC_BASE_URL` — external base URL used to build Stripe onboarding return/refresh
  links. When testing through a tunnel, set this to the public tunnel URL, otherwise
  Stripe redirects back to `localhost` and an external browser can't reach it.
- `FLASK_SECRET_KEY` — set a fixed value so login sessions survive restarts.

### Gotchas
- The landing page markup is inside `README.md`, not a standalone `.html` file; `app.py`
  strips the leading markdown heading and serves everything from `<!DOCTYPE` as HTML.
- Deps install with `pip install --break-system-packages` (PEP 668 externally-managed
  env); there is no virtualenv, and `python3.12-venv` is not guaranteed on fresh VMs.
- Stripe Connect onboarding redirects to Stripe and back to
  `PUBLIC_BASE_URL/connect/return`; localhost return URLs won't work from an external
  browser, so run behind a tunnel and set `PUBLIC_BASE_URL` for real onboarding.
- `POST /api/simulate-earning` funds the platform test balance via a `tok_bypassPending`
  charge, then `Transfer`s the 60% share to the connected account — a test-mode-only way
  to demonstrate the payout loop.
- The embedded HTML in `README.md` is truncated at the FAQ section with no trailing
  `<script>`, so JS-driven widgets on the landing page (industry tabs, mobile hamburger)
  don't toggle; navbar anchor links work via native scrolling. This is the repo's actual
  state, not an environment problem.

### Lint / test / build
There are no linters, automated tests, or build steps in this repo. Nothing to run.
