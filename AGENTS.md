# AGENTS.md

## Cursor Cloud specific instructions

### What this repo is
This repository is a single static marketing landing page ("HoldPay" / "waitgains").
The entire page markup lives inside `README.md`, which begins with a `# waitgains`
markdown heading followed by a full `<!DOCTYPE html> ... ` document. There is **no**
package manager, build system, or dependencies — only Python 3 (stdlib) is required,
which is preinstalled.

### Running the app (dev)
Use the bundled zero-dependency dev server, which reads `README.md`, strips the leading
markdown heading, and serves the HTML:

```
python3 serve.py --port 8000
```

Then open `http://localhost:8000/`. The server re-reads `README.md` on every request,
so edits show up on a browser refresh (no restart needed).

Gotchas:
- Do **not** open `README.md` directly in a browser or serve it with a plain static
  server (e.g. `python3 -m http.server`) expecting it to render — browsers treat `.md`
  as text/download. `serve.py` exists specifically to serve it as `text/html`.
- The HTML in `README.md` is truncated at the FAQ section and has no trailing
  `<script>`, so JS-driven widgets (industry tabs, mobile hamburger menu) do not toggle.
  This is the repo's actual state, not an environment problem. Same-page navbar anchor
  links (How It Works / Industries / Pricing) work via native browser scrolling.

### Lint / test / build
There are no linters, tests, or build steps in this repo (pure static HTML). Nothing to run.
