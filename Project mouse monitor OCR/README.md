# Mouse Monitor OCR

Mouse Monitor OCR is a local, human-in-the-loop application for transferring
daily mouse-monitoring measurements from photographed handwritten sheets into
an existing Excel workbook.

The application processes each table cell separately, proposes values for
`W`, `L`, and `Weight`, and presents them in a Streamlit review table. The user
can correct and approve each row before creating the final Excel file.

## Inputs

The application accepts:

- One or more phone images of daily monitoring sheets (`JPG`, `PNG`, or
  `TIFF`).
- The final Excel template that should receive the reviewed measurements.

Images can be uploaded through the sidebar. An Excel template can either be
selected from `data/templates/` or uploaded through the application.
For privacy, uploaded monitoring-sheet images are processed locally and the
upper-left group-name panel is masked automatically before the local working
copy is saved.

## Output

The generated workbook is saved as a new file under `data/output/`. The source
template is never overwritten.

The workbook keeps the template's existing rows, columns, empty rows, cage
blocks, formatting, formulas, merged cells, and ordering. Only these cells may
be filled for an approved mouse:

| Excel column | Measurement |
| --- | --- |
| K | W |
| L | L |
| M | Weight |

## Important processing rules

- Measurements are mapped to Excel rows by **mouse ID**, never by image or row
  order.
- Empty template rows remain empty. Rows are not deleted, inserted, sorted,
  shifted, or compressed.
- `0.00` is a valid measurement and is different from a missing value.
- Missing `W` or `L` is a strong warning and requires explicit approval of that
  row before export.
- Missing `Weight` is a warning but does not independently block export.
- If the whole Weight column appears empty on one photographed page, one
  page-level warning is shown.
- Out-of-range values require explicit approval before they can be written.
- Comments, crossed-out values, and side notes require manual review and are
  never approved automatically.
- Duplicate mouse IDs block processing by default. The GUI provides an explicit
  **Continue despite duplicate mouse IDs** override.
- A detected mouse ID that is absent from the template is skipped with a
  warning.
- A mouse that exists in the template but has no extracted data is left
  untouched.

## Installation and running

Python 3.11 is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, upload the images and template, and
click **Run extraction**. Review the proposed rows, edit values where needed,
approve only rows whose warnings should be overridden, and click **Export to
Excel**. Clean rows and rows missing only Weight do not require approval.

### Baseline OCR dependency

The replaceable baseline OCR backend uses `pytesseract`. The Python package is
listed in `requirements.txt`, but the Tesseract OCR desktop executable must
also be installed separately and its `tesseract` command must be available on
`PATH`.

If Tesseract is unavailable, the application fails safely: OCR values remain
missing with zero confidence and can still be handled through manual review.

## Folder structure

```text
mouse_monitor_ocr/
├── app.py                         # Streamlit entry point
├── requirements.txt
├── README.md
├── config/
│   └── settings.json              # Paths, Excel columns, and valid ranges
├── data/
│   ├── input_images/              # Safely named uploaded source images
│   ├── templates/                 # Final Excel templates
│   ├── output/                    # Generated Excel and learning ZIP files
│   ├── crops/                     # Per-cell OCR crops and debug images
│   └── learning_data/             # Locally stored correction metadata
├── src/
│   ├── config.py                  # Central configuration loader
│   ├── excel_template.py          # Mouse-ID-to-row mapping
│   ├── image_loader.py            # Image loading and preprocessing
│   ├── table_detection.py         # Table approximation and cell crops
│   ├── ocr_engine.py              # Replaceable OCR interface
│   ├── pipeline.py                # End-to-end extraction pipeline
│   ├── review_model.py            # Review and correction data models
│   ├── validation.py              # Ranges, warnings, and approval rules
│   ├── gui.py                     # Streamlit review interface
│   ├── learning_store.py          # Local correction storage and export
│   ├── train_handwriting_model.py # Future training-data preparation
│   └── export_excel.py            # Structure-preserving Excel export
└── tests/
```

The configured default template is `data/templates/Book1.xlsx`, sheet
`output`. Mouse IDs are expected in column `B`, beginning at row 9. If the real
workbook uses a different sheet, start row, or mouse ID column, update
`config/settings.json` before exporting.

## Learning data

When a reviewer changes a predicted `W`, `L`, or `Weight` value, the
application stores a local `FieldCorrection` record in:

```text
data/learning_data/corrections.csv
```

Each record includes the timestamp, source image, mouse ID, field name,
original prediction, corrected value, and the corresponding cell-crop path.
The correction and crop are also used by a local personal handwriting recognizer
on later extraction runs. The recognizer compares new handwritten numeric cells
against corrected examples from the same reviewer. This is intentionally local
and lightweight; it improves as more corrected examples are saved, but it is not
a replacement for human review.

The Settings section provides:

- **One-run learning reset** — clears only temporary learning state for the
  current run while retaining correction history.
- **Export learning data/model** — creates a ZIP containing correction
  metadata, a manifest, and available crop images.
- **Full learning reset** — deletes persisted learning data after explicit
  confirmation.

Learning data stays on the local computer unless the user explicitly exports
the ZIP.
Image contents are processed locally and are not uploaded to remote OCR
services by this workflow.

## Current limitations

- Phone-photo focus, lighting, shadows, rotation, and perspective directly
  affect table alignment and OCR quality.
- Handwritten values may be read incorrectly or with low confidence and can
  require manual correction.
- Table detection currently uses a fixed-layout approximation with a grid-based
  detector and relative-coordinate fallback.
- Comment and cross-out detection uses simple visual heuristics.
- The default Tesseract baseline is better suited to printed text than varied
  handwriting.
- A lightweight personal handwriting recognizer uses saved corrections as local
  templates, but a deeper handwriting model is not trained or fine-tuned yet.
