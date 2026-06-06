# Prompts and task definition for Day08 FastAPI app

## Original user request

- Clone Day06 into a new Day08 folder.
- Build a new web application for the same business logic.
- Prefer FastAPI instead of Streamlit or Flask.
- Support both HTML-like interactive UI and JSON-like output behavior.
- Use only search from data sources, not local input files.
- Add a protection layer against abuse such as CLI-style injection.
- Update README documentation.

## Implementation summary

- Created `Day08/web_antibody_search.py` as a FastAPI application.
- The app uses `search_all_sources()` and the existing `antibody_processing` logic.
- Added input validation for target queries and species filters.
- Added output generation for CSV and Excel, both saved locally and available via download routes.
- Added `Day08/test_web_antibody_search.py` to validate the FastAPI search endpoints and input validation.
- Updated `Day08/requirements.txt` and `Day08/README.md` for the new web app.
