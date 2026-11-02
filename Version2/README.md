# Patient Record System — Version 2 (refactored)

**Educational prototype only; use fictional patient data. Do not deploy with real medical records.**

## What changed from Version 1

| Requested fix | Files | Result |
| --- | --- | --- |
| Remove SQL from UI; enforce ownership | `suggestion_repository.py`, `ai_category_service.py`, `web_app.py` | `find_patient_id(UUID)` joins suggestion to note; doctor authorization occurs *before* checking ownership. `review_suggestion(suggestion_id, patient_id, *, accept, token)` raises `LookupError` when mismatched. |
| Avoid N+1 history lookups | Same files | `find_by_patient_id(UUID)` returns `dict[UUID, CategorySuggestion]` with **one JOIN query**. `get_suggestions_for_patient(patient_id, *, token)` authorizes **once**. |
| Remove old demo scripts | Project folder | Deleted `demo_stage3.py`, `demo_stage4.py`, `demo_stage5.py`. Temporary/demo database snapshots, generated caches, and demo ID text are excluded from the distribution. |
| Stop re-initializing schema per request | `web_app.py` | `create_app()` initializes the database **once**; `services()` opens request-local connections without running migrations. |
| Connect real Gemini Flash | `llm_category_classifier.py`, `ai_category_service.py`, `web_app.py`, `requirements.txt` | Uses Google's official `google-genai` SDK, JSON schema output, `GEMINI_API_KEY` from environment, explicit HTTP timeout, validation, and `UNCERTAIN` for low self-reported confidence. Keyword demo fallback remains available without a key. |

## Install and run (Python 3.10+)

Unzip the project, then from the extracted folder:

```powershell
python -m pip install -r requirements.txt
python bootstrap_staff.py --username doctor1 --role doctor
python web_app.py
```

Enter a 12+ character password when prompted. Open `http://127.0.0.1:5000` and sign in. Create a fictional patient, open that patient's record, save a fictional visit note, and click **Request optional AI category**. A doctor can approve or reject a pending suggestion. Notes remain saved even when AI fails. The app creates `prs_web.db` the first time it starts; keep this file if you want your fictional records to persist across restarts.

### Connect Gemini Flash (free-tier eligible)

1. Create an API key at [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Install dependencies using the command above (`google-genai` is included in `requirements.txt`).
3. Set the key in your terminal **before** starting the application:

**Windows PowerShell**
```powershell
$env:GEMINI_API_KEY = "YOUR_KEY_HERE"
python web_app.py
```

**Windows Command Prompt**
```cmd
set GEMINI_API_KEY=YOUR_KEY_HERE
python web_app.py
```

**macOS / Linux**
```bash
export GEMINI_API_KEY="YOUR_KEY_HERE"
python web_app.py
```

Do **not** put an API key in source code, commit it to Git, share it with your professor, or include it in the ZIP. The key is read from the environment on startup. If the key is set, Gemini Flash is selected; if it is not, the app uses the deterministic keyword classifier and visibly labels the fallback mode. A configured but failed Gemini request results in `UNAVAILABLE`, not a hidden keyword-generated diagnosis.

Default Gemini model: `gemini-3.8-flash` (configurable with `PRS_GEMINI_MODEL`). Default AI timeout: `6` seconds (configurable with `PRS_AI_TIMEOUT`). The API client uses its own HTTP timeout and the service imposes an outer timeout; a timed-out worker may briefly continue finishing a request, but it cannot edit database records. The app will not run inference on a saved note again once a suggestion result is stored; create another fictional visit note to demonstrate another outcome.

**Important safety limitation:** Google may use content from free-tier API requests to improve its products. The program sends the visit-note text to Google when an authorized user clicks **Request optional AI category** while Gemini is configured. **Never transmit real patient information or protected health information through this prototype.** Gemini's `confidence` is the model's self-reported estimate, not a calibrated or clinically verified probability; a score below `0.70` results in `UNCERTAIN`. **This is categorization, not medical diagnosis or treatment guidance.** Free-tier availability, quotas, and model access depend on the Google project and may change.

### Offline fallback

Without `GEMINI_API_KEY`, `KeywordAIClient` performs keyword matching for demonstrations. Unlike Version 1, ambiguous or unmatched notes can yield low confidence and `UNCERTAIN`. The UI labels the current AI mode. Keyword scores are heuristic and do not represent learned probabilities.

## Tests

```bash
python -m unittest discover -v
```

`test_version2.py` adds offline regression tests for authorization ordering, patient ownership, a single JOIN and one authorization on history retrieval, Gemini structured results using a **fake SDK client** (no key and no network required), uncertainty, error recovery, and fallback mode. `test_stage6.py` includes Flask web-route tests and schema initialization verification; these require Flask to be installed.

**API integration testing:** Automated tests mock Gemini responses; no live Gemini call is made without an API key. To verify live operation, set `GEMINI_API_KEY` and perform a classification using fictional text. Actual API model availability and free-tier limits must be verified in your Google project.

## Remaining limitations

The project still lacks production-grade clinical compliance, validated consent, full auditing, encrypted data storage, patient-assignment authorization, rate limiting, and medically calibrated AI. It is not HIPAA-ready. The optional AI service cannot affect note persistence. Older schema migration is not necessary for the current schema; this refactor preserves the Version 1 table structure.
