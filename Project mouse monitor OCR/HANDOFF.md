# HANDOFF

Last updated: 2026-07-10

## Project goal

Mouse Monitor OCR is a local, privacy-preserving, human-in-the-loop tool for:

- taking phone photos of mouse tumor monitoring sheets,
- extracting `mouse_id`, `W`, `L`, and `Weight`,
- letting the reviewer correct OCR mistakes in a Streamlit GUI,
- exporting the approved values into an existing Excel workbook without changing the workbook structure.

The intended workflow is:

1. Upload images and an Excel template.
2. Run extraction.
3. Review and correct all rows.
4. Commit the reviewed rows.
5. Export only after validation rules are satisfied or explicitly approved.


## What has already been implemented

### End-to-end app flow

- Local Streamlit app entry point in `app.py`.
- Windows launcher scripts: `run_app.ps1`, `run_app.bat`, `run_tests.ps1`.
- Image upload, template selection/upload, extraction, review, approval, and export flow in `src/gui.py`.

### OCR and extraction pipeline

- Image loading and sanitization in `src/image_loader.py`.
- Automatic masking/redaction of the upper-left group-name panel before processing saved copies.
- Table detection and per-cell cropping in `src/table_detection.py`.
- OCR engine in `src/ocr_engine.py` with:
  - Tesseract baseline OCR,
  - optional local PaddleOCR support,
  - local correction-based handwriting fallback for numeric fields.
- End-to-end extraction orchestration in `src/pipeline.py`.

### Review UX

- Editable review table for `mouse_id`, `W`, `L`, and `Weight`.
- Custom Streamlit component in `src/review_table_component.py` for more Excel-like keyboard navigation.
- Draft edits stay separate from the export table until the user explicitly updates/commits them.

### Validation and export

- Validation logic in `src/validation.py`:
  - `0.00` is valid,
  - blank/empty/`None` means missing,
  - missing `W`/`L` is blocking unless explicitly approved,
  - missing `Weight` is warning-only,
  - out-of-range values are flagged,
  - page-level warning if an entire Weight column is empty.
- Structure-preserving Excel export in `src/export_excel.py`.
- Mapping to Excel is done by `mouse_id`, not by row position.
- Source workbook is never overwritten.

### Learning / correction persistence

- User corrections are saved locally in `data/learning_data/`.
- Learning storage logic is in `src/learning_store.py`.
- If `corrections.csv` is temporarily locked, the app falls back to `corrections_pending.csv`.
- On startup, split learning files can be consolidated back into one canonical `corrections.csv`.
- Learning export ZIP and reset actions are exposed in the GUI.

### Robustness work already added

- Fallback to temporary folders when project folders are not writable:
  - uploaded templates,
  - input images,
  - crops,
  - output workbooks.
- Duplicate extracted mouse IDs stop processing by default, with an explicit override path in the GUI.
- Missing `mouse_id` values are no longer auto-inferred from neighboring rows.

### Test coverage

- Automated tests exist for config, OCR helpers, pipeline behavior, GUI validation flow, Excel export, learning storage, sample integration, and training-data preparation.
- Latest full suite result during the last integration pass:
  - `116 passed in 6.06s`


## Important design decisions

- **Local-only processing:** the workflow is designed to keep images and OCR local. No remote OCR service is required.
- **Map by mouse ID only:** export writes by `mouse_id`, never by image order or row order.
- **Do not guess missing IDs:** if printed `mouse_id` OCR fails, the value stays missing for manual review.
- **Batch correction flow:** user edits are staged first; downstream export data is updated only after an explicit action.
- **Preserve workbook structure:** no row insertion, deletion, sorting, shifting, or compression.
- **Zero is valid:** `0`, `0.0`, and `0.00` must never be treated as missing.
- **Writable-folder fallbacks are intentional:** if project `data/` subfolders are locked, the app should still run using temp folders instead of crashing.
- **Learning layer is lightweight:** the current “learning” behavior is based on saved correction examples and local matching/fallback logic. It is not yet a deeply trained handwriting model.
- **Privacy redaction happens before local saved working copies:** uploaded images are masked to remove group-name labels before the app stores its local processing copies.


## Files that were changed

The most important implementation and stabilization files touched in the recent work are:

- `app.py`
- `README.md`
- `requirements.txt`
- `requirements-paddle.txt`
- `run_app.ps1`
- `run_app.bat`
- `run_tests.ps1`
- `config/settings.json`
- `src/gui.py`
- `src/review_table_component.py`
- `src/pipeline.py`
- `src/image_loader.py`
- `src/ocr_engine.py`
- `src/paddle_handwriting_ocr.py`
- `src/learning_store.py`
- `src/validation.py`
- `src/export_excel.py`
- `tests/test_gui.py`
- `tests/test_pipeline.py`
- `tests/test_image_loader.py`
- `tests/test_learning_store.py`
- `tests/test_sample_integration.py`
- `tests/test_acceptance_pytest.py`
- additional supporting tests under `tests/`

Recent high-signal bug-fix files:

- `src/gui.py`
- `src/pipeline.py`
- `src/image_loader.py`
- `tests/test_gui.py`
- `tests/test_pipeline.py`
- `tests/test_image_loader.py`


## Remaining tasks

1. Improve printed `mouse_id` OCR accuracy.
   - This is still the most important weak point.
   - Likely next step: stronger preprocessing dedicated to the printed-ID column only.

2. Improve empty-cell detection.
   - The app still confuses some empty handwritten cells with faint numbers/noise.

3. Improve comment / crossed-out / side-note discrimination.
   - Current heuristics are useful but still noisy on real phone photos.

4. Re-validate keyboard behavior in the real browser.
   - The custom table component implements Excel-like `Tab` / `Enter` movement, but this still needs real-user confirmation in the running app.

5. Continue benchmarking on the provided sample workbook/images.
   - Compare extraction results against `Sample.xlsx` sheets `output 1` and `output 2`.

6. Decide whether to go beyond the current lightweight learning approach.
   - If future accuracy is still not good enough, the next step would be a stronger local handwriting model or a better training pipeline built from saved corrections.


## Known bugs and unresolved questions

### Known issues

- OCR accuracy is still inconsistent on some phone-photo inputs, especially for printed `mouse_id`.
- Duplicate `mouse_id` extraction can still happen on noisy inputs.
- If Tesseract is not installed, printed mouse-ID recognition becomes much weaker or unavailable depending on the environment.
- Some machines/folders may deny writes to `data/templates`, `data/input_images`, `data/crops`, or `data/output`.
  - The app now falls back to temp folders instead of crashing.
  - This means some outputs may be saved outside the project folder when permissions are restricted.

### Open questions

- Is the current custom review-table keyboard behavior fully acceptable in the browser the user actually uses?
- Is the current group-name redaction always safe across all page layouts, or are there still edge cases near cage 1 / cage 2?
- Is the current printed-ID stack good enough if the sheet is printed with a white background, or do we still need a dedicated printed-text OCR pass regardless?
- Should the next major accuracy push focus on:
  - better preprocessing,
  - stronger printed-ID OCR,
  - or deeper handwriting-model training?


## How to run the project

### Recommended Windows launcher

Double-click:

- `run_app.bat`

or in PowerShell:

```powershell
.\run_app.ps1
```

The app starts locally at:

```text
http://localhost:8501
```

### Manual setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### Optional PaddleOCR environment

If you want the local PaddleOCR path as well:

```powershell
python -m venv .venv-paddle
.venv-paddle\Scripts\Activate.ps1
pip install -r requirements-paddle.txt
```

Notes:

- `requirements-paddle.txt` includes `paddlepaddle==3.3.0` and `paddleocr==3.7.0`.
- Tesseract is still a separate desktop install and must be available on `PATH` for the Tesseract backend to work.


## How to test the project

### Full QA

```powershell
.\run_tests.ps1 -Mode Full
```

or:

```powershell
pytest -q
```

### Quick QA

```powershell
.\run_tests.ps1 -Mode Quick
```

This runs:

```powershell
pytest -m "not full" -q
```

### Useful test areas

- GUI and validation behavior:
  - `tests/test_gui.py`
  - `tests/test_validation.py`
- OCR pipeline behavior:
  - `tests/test_pipeline.py`
  - `tests/test_ocr_engine.py`
  - `tests/test_paddle_handwriting_ocr.py`
- Learning storage:
  - `tests/test_learning_store.py`
  - `tests/test_handwriting_ocr.py`
- Export rules:
  - `tests/test_export_excel.py`
  - `tests/test_excel_template.py`
- Sample-based integration:
  - `tests/test_sample_integration.py`


## Recommended next step

If development continues from here, the best next step is:

1. build a narrow benchmark for printed `mouse_id` accuracy,
2. improve preprocessing for that column only,
3. re-run the sample integration tests and compare against `Sample.xlsx`.
