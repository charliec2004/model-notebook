# Agent setup instructions

Help a non-technical user run this project locally. Preserve its small, dependency-free design.

## Local setup

1. Clone/download this repository into a normal project folder. Locate `server.py` and read `README.md` and `docs/SETUP.md`.
2. Check the OS and Python version: `python3 --version` on macOS/Linux; `py --version` on Windows. Python 3.9+ is supported. If missing, guide the user through the official python.org installer; do not silently change system packages or use administrator privileges.
3. No dependency installation is needed. Do not add a framework, database, Node runtime, package manager, or deployment service.
4. Run `python3 -m unittest discover -s tests -v` (Windows: `py -m unittest discover -s tests -v`). Tests are offline and use fake API responses.
5. Start `python3 server.py` (Windows: `py server.py`) in a persistent terminal/session. Open `http://127.0.0.1:8000` for the user. If occupied, use `--port 8001` and its corresponding URL; do not kill an unrelated process.
6. Confirm the page loads, the live model selector populates, and the controls are usable. A failed catalog fetch is a connection problem, not a confirmed empty catalog.

## Help the user get a key

- Explain that an OpenRouter key is a private credential, and featured models generally cost credits per request.
- Web search uses that same key and adds search charges when used. It is off by default. Explain the cost before a live test, show returned source links, and distinguish enabled search from reported search usage. Do not enable it or make a billable test without the user's authorization.
- Guide the user to https://openrouter.ai/settings/keys after they sign in. Have them create a key named Model Notebook, choose a small spending limit, and copy it into the local app themselves. Use `docs/SETUP.md` for the walkthrough.
- Never ask them to paste their key, password, or payment details into chat. Never read or print their key, commit it, put it in a URL, or save it to a file. Prefer the UI key field; an environment/secret-manager key is also supported when the user prefers it.
- Creating an account, handling payment details, buying credits, or enabling top-ups is for the user. Do not do those actions as part of setup.
- A live run can cost money and sends the question to OpenRouter and a provider. Have the user click Run themselves unless they explicitly authorize a particular live test. Offline verification does not need a real key.
- After their first successful run, show how to change models while keeping the same question, revisit a saved response, export JSON, and remove/undo. Explain that keys clear on reload and responses are saved to that browser/host/port.
- Give the exact restart command, URL, and Ctrl+C stop instructions. Do not claim a live model run passed if only offline tests passed.

## If editing

Keep the server bound to loopback and preserve session authentication, Host/Origin checks, fixed upstream URLs, input limits, plain-text rendering, and credential exclusion from storage/exports. Do not expose it publicly or create a tunnel. Keep one independent user prompt per run and preserve requested/returned model IDs. Inspect any UI changes at desktop and narrow widths and verify affected interactions through saved results. Source lives in `server.py` and `static/`; tests live in `tests/`.
