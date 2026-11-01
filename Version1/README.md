# PRS Stage 6 — Flask UI (fictional patient data only)

Includes all Stage 1–5 Python classes and tests, plus a Flask browser interface.

## Setup

Python 3.10+ recommended. In the extracted folder:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python bootstrap_staff.py --username doctor1 --role doctor
# Enter a 12+ character password at the prompt.
python web_app.py
```

Open http://127.0.0.1:5000 in the browser. Sign in and create a fictional patient. The database file `prs_web.db` persists between runs. To add clinical staff, run `python bootstrap_staff.py --username nurse1 --role clinical_staff`.

## Pages
- `/login`: Staff login
- `/patients`: Search patient by immutable UUID
- `/patients/new`: Register patient
- `/patients/<UUID>`: View patient and immutable visit history, write notes, request optional AI categorization
- `/patients/<UUID>/edit`: Explicit consent checkbox for demographic updates
- Doctor-only AI accept/reject controls (backend authorization is enforced)

## Testing

```bash
python -m unittest discover -v
```

`test_stage6.py` uses Flask's test client. Stage 1–5 tests are retained.

## Security scope / limitations

**NOT for real patient data.** Educational prototype only. Session token is stored in Flask's signed cookie (HttpOnly, SameSite=Lax), so configure HTTPS (`PRS_SECURE_COOKIE=1`) and a stable random `PRS_SECRET_KEY` for any nonlocal deployment. HTTPS, application-wide audit logging, verified consent, rate limiting, database encryption, record access restrictions, deployment hardening and clinical validation are out of scope. Account bootstrap must only be available to trusted administrators of the running host. Do not publish `prs_web.db` or secret keys. A keyword-based demonstration stub is used instead of real clinical AI.

SQLite DB connections are request-local. CSRF tokens are checked on every POST. Session expiration is enforced server-side by the existing Stage 4 authentication service. Run locally using the built-in development server; do not expose it to the internet.
