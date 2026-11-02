# Version 2 — Refactoring evidence

This document is intended to help explain the concrete changes from Version 1 in Assignment #4.

## 1. Encapsulate suggestion ownership
- **Before:** `web_app.review()` directly executed a SQL JOIN against `category_suggestions` and `visit_notes`.
- **After:** `SuggestionRepository.find_patient_id(suggestion_id) -> UUID | None`; `AICategoryService.review_suggestion(suggestion_id, patient_id, *, accept, token)` checks the doctor's role before querying ownership and raises `LookupError` if the suggestion is not owned by the URL patient.
- **Why:** Avoids SQL logic in the presentation layer and stops cross-patient review attempts.
- **Evidence:** `test_version2.py`: `test_wrong_patient_cannot_review_suggestion`, `test_authorization_before_ownership_query`.

## 2. Batch history lookup
- **Before:** `web_app.patient_detail()` called `get_suggestion()` once for each note, re-authorizing and re-loading the note repeatedly.
- **After:** `SuggestionRepository.find_by_patient_id(patient_id)` executes one JOIN and returns `{note_uuid: CategorySuggestion}`. `AICategoryService.get_suggestions_for_patient()` performs a single authorization. The UI converts UUID keys to strings for the existing Jinja template.
- **Why:** Avoid N+1 query behavior.
- **Evidence:** `test_batch_history_one_join_and_authorization_once` traces SELECT queries and verifies exactly one JOIN plus one authorization; Flask route check in `test_stage6.py`.

## 3. Remove redundant demos
- Deleted `demo_stage3.py`, `demo_stage4.py`, `demo_stage5.py`.
- Demo database files, `__pycache__`, and generated identifier text were also excluded from the ZIP; no prepopulated patient/staff database is distributed.

## 4. Move schema initialization
- **Before:** `services()` called `DatabaseConnection.initialize_schema()` each time a request first opened a database connection.
- **After:** `create_app()` calls it once at application startup, closes the initialization connection, and retains request-local SQLite connections for later operations.
- **Evidence:** `test_schema_initializes_at_app_creation_once` (requires Flask).

## 5. Add Gemini Flash
- `llm_category_classifier.py` adds `LLMCategoryClassifier.predict()` with structured output using the official `google-genai` SDK, a configurable Flash model, and HTTP timeout.
- `web_app.create_app()` uses Gemini when `GEMINI_API_KEY` is set; otherwise it selects the labeled offline `KeywordAIClient` demo fallback.
- `AICategoryService.suggest_category()` validates model output and stores `UNCERTAIN` when the returned confidence is below the threshold, or `UNAVAILABLE` when the model fails or times out. The original visit note remains saved and immutable.
- Keyword scores now vary with ambiguous or missing keyword evidence; their values are heuristic, not calibrated.
- **Evidence:** `test_version2.py` includes fake SDK tests for valid/low-confidence/malformed responses and offline fallback. These do not require a key or network connection.

## Test status in authoring environment

`python -m unittest discover -v`: **68 total, 60 passed, 8 skipped** (Flask unavailable locally, package index blocked). The backend and simulated Gemini tests all pass. Live Gemini calls were not made because no API key was provided. On the professor's machine, install `requirements.txt` and rerun the suite, including the Flask routes.
