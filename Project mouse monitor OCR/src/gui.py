"""Streamlit interface for cell-based OCR review and validated Excel export."""

from datetime import datetime
from dataclasses import replace
import math
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd
import streamlit as st

from .config import Config, DEFAULT_SETTINGS_PATH, PROJECT_ROOT
from .excel_template import validate_xlsx_upload
from .export_excel import export_validated_measurements_to_excel
from .image_loader import load_uploaded_images
from .learning_store import (
    consolidate_learning_files,
    export_learning_data,
    reset_learning_data,
    reset_learning_for_current_run_only,
    save_correction,
)
from .pipeline import (
    DuplicateExtractedMouseIDError,
    ExtractionPipelineResult,
    extract_measurements_from_images,
)
from .review_table_component import render_review_table
from .review_model import ExtractedMeasurement, FieldCorrection
from .validation import DEFAULT_RANGES, ValidationStatus, validate_page


VISIBLE_COLUMNS = [
    "source_image",
    "cage_number",
    "mouse_id",
    "ear_marking",
    "W",
    "L",
    "Weight",
    "warnings",
    "requires_manual_review",
]
INTERNAL_COLUMNS = [
    "comment_detected",
    "crossed_out_or_side_note_detected",
    "page_row",
    "original_W",
    "original_L",
    "original_Weight",
    "crop_W",
    "crop_L",
    "crop_Weight",
]
FIELD_LIMITS = {
    field_name: limits[1] for field_name, limits in DEFAULT_RANGES.items()
}
CELL_COLORS = {
    "missing_required": "#ffd6d6",
    "missing_weight": "#fff3bf",
    "out_of_range": "#ffe1bf",
    "negative": "#ff9f9f",
    "note": "#eadcff",
}
REVIEW_TABLE_EDITABLE_COLUMNS = ["mouse_id", "W", "L", "Weight"]
REVIEW_TABLE_LABELS = {
    "source_image": "source_image",
    "cage_number": "cage_number",
    "mouse_id": "mouse_id",
    "ear_marking": "ear_marking",
    "W": "W",
    "L": "L",
    "Weight": "Weight",
    "warnings": "warnings",
    "requires_manual_review": "manual_review",
}


def render_app() -> None:
    """Render the complete basic human-in-the-loop review interface."""
    st.set_page_config(page_title="Mouse Monitor OCR", layout="wide")
    _initialize_session_state()
    st.title("Mouse Monitor OCR")
    st.caption("Local cell-based OCR workflow with mandatory human review.")

    controls = _render_sidebar()
    if controls["run_extraction"]:
        _run_extraction(
            controls["images"],
            debug_table=controls["debug_table"],
        )

    _render_duplicate_override()
    _render_extraction_messages()

    st.subheader("Measurement review")
    if st.session_state.draft_review_rows.empty:
        st.info("Upload one or more images and click **Run extraction** to create OCR review rows.")
    else:
        with st.form(
            f"review_form_{st.session_state.editor_generation}",
            border=False,
        ):
            edited = _render_review_editor(st.session_state.draft_review_rows)
            update_export = st.form_submit_button(
                "Update export table",
                type="primary",
            )

        if update_export:
            edited = _restore_internal_columns(
                edited,
                st.session_state.draft_review_rows,
            )
            _save_gui_corrections(edited)
            committed_rows, _, _ = _commit_review_rows(edited)
            st.session_state.review_rows = committed_rows
            st.session_state.draft_review_rows = committed_rows.copy()
            st.session_state.editor_generation += 1
            _reset_warning_approval_state()
            st.success("Export table was updated from the reviewed corrections.")

        st.subheader("Export table")
        if st.session_state.review_rows.empty:
            st.info("Update the export table before exporting to Excel.")
        else:
            records, page_warnings = _records_from_dataframe(st.session_state.review_rows)
            _render_highlighted_overview(st.session_state.review_rows)
            _render_validation_summary(records, page_warnings)
            _render_export_approval_controls(st.session_state.review_rows, records)

    if controls["export"]:
        if _has_uncommitted_review_changes(
            st.session_state.draft_review_rows,
            st.session_state.review_rows,
        ):
            st.error("Update the export table before exporting to Excel.")
        else:
            _export_reviewed_rows(controls["template_path"])
    _render_latest_export()


def _initialize_session_state() -> None:
    """Create stable per-browser-session state used by Streamlit reruns."""
    if "review_rows" not in st.session_state:
        st.session_state.review_rows = pd.DataFrame(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS)
    else:
        st.session_state.review_rows = _normalize_review_dataframe(
            st.session_state.review_rows
        )
    if "draft_review_rows" not in st.session_state:
        st.session_state.draft_review_rows = pd.DataFrame(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS)
    else:
        st.session_state.draft_review_rows = _normalize_review_dataframe(
            st.session_state.draft_review_rows
        )
    if "editor_generation" not in st.session_state:
        st.session_state.editor_generation = 0
    if "latest_export" not in st.session_state:
        st.session_state.latest_export = None
    if "learning_message" not in st.session_state:
        st.session_state.learning_message = None
    if "pending_duplicate_result" not in st.session_state:
        st.session_state.pending_duplicate_result = None
    if "pending_duplicate_message" not in st.session_state:
        st.session_state.pending_duplicate_message = None
    if "duplicate_override_enabled" not in st.session_state:
        st.session_state.duplicate_override_enabled = False
    if "extraction_messages" not in st.session_state:
        st.session_state.extraction_messages = []
    if "debug_alignment_files" not in st.session_state:
        st.session_state.debug_alignment_files = []
    if "saved_correction_keys" not in st.session_state:
        st.session_state.saved_correction_keys = set()
    if "latest_learning_export" not in st.session_state:
        st.session_state.latest_learning_export = None
    if "learning_store_initialized" not in st.session_state:
        st.session_state.learning_store_initialized = True
        try:
            if consolidate_learning_files():
                st.session_state.learning_message = (
                    "Learning files were merged into one corrections.csv file."
                )
        except (FileNotFoundError, PermissionError, ValueError) as exc:
            st.session_state.learning_message = (
                f"Learning file merge failed: {exc}"
            )


def _normalize_review_dataframe(rows: pd.DataFrame) -> pd.DataFrame:
    """Drop stale columns from older GUI versions and restore the current schema."""
    if not isinstance(rows, pd.DataFrame):
        return pd.DataFrame(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS)
    normalized = rows.reindex(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS).copy()
    return normalized


def _render_sidebar() -> dict[str, Any]:
    """Render upload, export, and learning controls in the sidebar."""
    with st.sidebar:
        st.header("Inputs")
        uploaded_images = st.file_uploader(
            "Upload monitoring-sheet images",
            type=["jpg", "jpeg", "png", "tif", "tiff"],
            accept_multiple_files=True,
        )
        st.caption(
            "Images are processed locally. The upper-left group-name panel is masked automatically before local storage."
        )
        images = list(uploaded_images) if uploaded_images else []

        templates_folder = PROJECT_ROOT / "data" / "templates"
        available_templates = sorted(templates_folder.glob("*.xlsx"))
        selected_template: Path | None = None
        if available_templates:
            selected_name = st.selectbox(
                "Select final Excel template",
                [path.name for path in available_templates],
            )
            selected_template = templates_folder / selected_name
        else:
            st.caption("No Excel template is currently stored in data/templates.")

        uploaded_template = st.file_uploader(
            "Or upload final Excel template",
            type=["xlsx"],
            accept_multiple_files=False,
        )
        if uploaded_template is not None:
            try:
                selected_template, template_storage_warning = _stage_uploaded_template(
                    uploaded_template
                )
                st.caption(f"Using uploaded template: {uploaded_template.name}")
                if template_storage_warning:
                    st.warning(template_storage_warning)
            except (OSError, TypeError, ValueError) as exc:
                st.error(f"Excel template upload failed: {exc}")

        debug_table = st.checkbox(
            "Save table-alignment debug images",
            help="Draw and save every expected OCR cell rectangle in data/crops.",
        )

        run_extraction = st.button("Run extraction", type="primary", width="stretch")
        export = st.button("Export to Excel", width="stretch")

        st.divider()
        st.subheader("Settings")
        if st.button("One-run learning reset", width="stretch"):
            reset_learning_for_current_run_only()
            _rebase_review_predictions()
            _reset_warning_approval_state()
            st.session_state.saved_correction_keys = set()
            st.session_state.learning_message = "One-run learning state was reset."

        if st.button("Export learning data/model", width="stretch"):
            learning_zip = PROJECT_ROOT / "data" / "output" / (
                f"learning_data_{datetime.now():%Y%m%d_%H%M%S_%f}.zip"
            )
            try:
                st.session_state.latest_learning_export = export_learning_data(
                    learning_zip
                )
                st.session_state.learning_message = "Learning data ZIP was created."
            except (FileNotFoundError, FileExistsError, ValueError) as exc:
                st.session_state.learning_message = f"Learning export failed: {exc}"

        learning_export = st.session_state.latest_learning_export
        if learning_export and Path(learning_export).is_file():
            st.download_button(
                "Download learning data ZIP",
                data=Path(learning_export).read_bytes(),
                file_name=Path(learning_export).name,
                mime="application/zip",
                width="stretch",
            )

        confirm_full_reset = st.checkbox("Confirm full learning reset")
        if st.button(
            "Full learning reset",
            disabled=not confirm_full_reset,
            width="stretch",
        ):
            reset_learning_data()
            _rebase_review_predictions()
            _reset_warning_approval_state()
            st.session_state.latest_learning_export = None
            st.session_state.saved_correction_keys = set()
            st.session_state.learning_message = "Full learning state was reset."

        if st.session_state.learning_message:
            if "failed:" in st.session_state.learning_message.lower():
                st.error(st.session_state.learning_message)
            else:
                st.success(st.session_state.learning_message)

    return {
        "images": images or [],
        "template_path": selected_template,
        "run_extraction": run_extraction,
        "export": export,
        "debug_table": debug_table,
    }
def _stage_uploaded_template(uploaded_template: Any) -> tuple[Path, str | None]:
    """Store an uploaded workbook and fall back to a temp folder when needed."""
    safe_name = Path(uploaded_template.name).name
    destination = PROJECT_ROOT / "data" / "templates" / f"uploaded_{safe_name}"
    content = uploaded_template.getvalue()
    validate_xlsx_upload(content)
    warning: str | None = None
    try:
        _write_uploaded_template_copy(destination, content)
    except PermissionError:
        fallback_folder = _temporary_runtime_folder("templates")
        destination = fallback_folder / f"uploaded_{safe_name}"
        _write_uploaded_template_copy(destination, content)
        warning = (
            f"data/templates is not writable; using temporary folder {fallback_folder}."
        )
    return destination, warning


def _write_uploaded_template_copy(destination: Path, content: bytes) -> None:
    """Write a staged template only when the on-disk bytes differ."""
    if not destination.exists() or destination.read_bytes() != content:
        destination.write_bytes(content)


def _run_extraction(
    images: list[Any],
    *,
    debug_table: bool = False,
) -> None:
    """Load uploads and run table detection, cell OCR, models, and validation."""
    if not images:
        st.error("Upload at least one image before running extraction.")
        return
    try:
        loaded_images = load_uploaded_images(images)
        storage_warnings: list[str] = []
    except PermissionError:
        fallback_input = _temporary_runtime_folder("input_images")
        loaded_images = load_uploaded_images(images, fallback_input)
        storage_warnings = [
            f"data/input_images is not writable; using temporary folder {fallback_input}."
        ]
    except (FileNotFoundError, TypeError, ValueError) as exc:
        st.error(f"Image loading failed: {exc}")
        return
    try:
        result = extract_measurements_from_images(
            loaded_images,
            debug_table=debug_table,
            allow_duplicate_mouse_ids=False,
        )
    except PermissionError:
        fallback_crops = _temporary_runtime_folder("crops")
        storage_warnings.append(
            f"data/crops is not writable; using temporary folder {fallback_crops}."
        )
        try:
            result = extract_measurements_from_images(
                loaded_images,
                crops_folder=fallback_crops,
                debug_table=debug_table,
                allow_duplicate_mouse_ids=False,
            )
        except DuplicateExtractedMouseIDError as exc:
            st.session_state.pending_duplicate_result = exc.result
            st.session_state.pending_duplicate_message = str(exc)
            st.session_state.review_rows = pd.DataFrame(
                columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS
            )
            st.session_state.draft_review_rows = pd.DataFrame(
                columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS
            )
            st.session_state.duplicate_override_enabled = False
            return
    except DuplicateExtractedMouseIDError as exc:
        st.session_state.pending_duplicate_result = exc.result
        st.session_state.pending_duplicate_message = str(exc)
        st.session_state.review_rows = pd.DataFrame(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS)
        st.session_state.draft_review_rows = pd.DataFrame(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS)
        st.session_state.duplicate_override_enabled = False
        return
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        st.error(f"OCR pipeline failed: {exc}")
        return
    result = replace(
        result,
        system_warnings=[*storage_warnings, *result.system_warnings],
    )
    _apply_pipeline_result(result, duplicate_override=False)


def _temporary_runtime_folder(name: str) -> Path:
    """Create a local fallback when project data folders are read-only."""
    folder = Path(tempfile.gettempdir()) / "mouse_monitor_ocr" / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _apply_pipeline_result(
    result: ExtractionPipelineResult,
    *,
    duplicate_override: bool,
) -> None:
    """Move a completed or explicitly overridden pipeline result into review state."""
    rows = _records_to_dataframe(
        result.measurements, correction_contexts=result.correction_contexts
    )
    st.session_state.review_rows = rows
    st.session_state.draft_review_rows = rows.copy()
    st.session_state.editor_generation += 1
    _reset_warning_approval_state()
    st.session_state.pending_duplicate_result = None
    st.session_state.pending_duplicate_message = None
    st.session_state.duplicate_override_enabled = duplicate_override
    debug_files = [
        str(table.debug_image_path)
        for table in result.table_results
        if table.debug_image_path is not None
    ]
    st.session_state.extraction_messages = [
        *(
            f"Storage: {warning}"
            if "not writable" in warning
            else f"OCR backend: {warning}"
            for warning in result.system_warnings
        ),
    ]
    st.session_state.debug_alignment_files = debug_files
    crop_count = sum(len(table.cells) for table in result.table_results)
    st.success(
        f"OCR pipeline processed {len(result.table_results)} image(s), saved "
        f"{crop_count} cell crop(s), and created {len(result.measurements)} review row(s)."
    )


def _render_duplicate_override() -> None:
    """Stop on duplicates by default and expose one explicit continuation action."""
    pending = st.session_state.pending_duplicate_result
    if pending is None:
        return
    st.error(st.session_state.pending_duplicate_message)
    if st.button(
        "Continue despite duplicate mouse IDs",
        type="primary",
        help="Duplicates will remain visible for manual review and export will use the first occurrence.",
    ):
        _apply_pipeline_result(pending, duplicate_override=True)
        st.warning(
            "Duplicate override enabled. Review duplicate rows carefully before approval."
        )


def _render_extraction_messages() -> None:
    """Keep page and OCR-backend warnings visible across Streamlit reruns."""
    for message in st.session_state.extraction_messages:
        if "tesseract is not installed" in message.lower():
            st.info(
                "Printed mouse ID recognition is unavailable because Tesseract "
                "is not installed. Personal handwriting recognition for W, L, "
                "and Weight remains active."
            )
        else:
            st.warning(message)

    debug_files = st.session_state.debug_alignment_files
    if debug_files:
        with st.expander("Technical alignment details"):
            st.caption("Debug images were saved for checking table alignment:")
            for path in debug_files:
                st.code(path, language=None)


def _render_review_editor(rows: pd.DataFrame) -> pd.DataFrame:
    """Render the editable review table with custom keyboard navigation."""
    component_key = f"review_editor_{st.session_state.editor_generation}"
    visible_rows = rows.reindex(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS).copy()
    return render_review_table(
        visible_rows,
        key=component_key,
        visible_columns=VISIBLE_COLUMNS,
        editable_columns=REVIEW_TABLE_EDITABLE_COLUMNS,
        column_labels=REVIEW_TABLE_LABELS,
        cell_backgrounds=_review_cell_backgrounds(visible_rows),
    )


def _render_highlighted_overview(rows: pd.DataFrame) -> None:
    """Show a fully styled read-only overview beside the editable review workflow."""
    st.markdown("**Highlighted export overview**")
    normalized_rows = _normalize_review_dataframe(rows)
    styled = normalized_rows.style.apply(_highlight_review_row, axis=1).hide(
        axis="columns", subset=INTERNAL_COLUMNS
    )
    st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        column_config={
            "W": st.column_config.NumberColumn("W", format="%.2f"),
            "L": st.column_config.NumberColumn("L", format="%.2f"),
            "Weight": st.column_config.NumberColumn("Weight", format="%.2f"),
        },
    )


def _review_cell_backgrounds(rows: pd.DataFrame) -> list[dict[str, str]]:
    """Return per-row cell background colors for the editable review table."""
    backgrounds: list[dict[str, str]] = []
    for _, row in rows.iterrows():
        row_backgrounds: dict[str, str] = {}
        for field_name, maximum in FIELD_LIMITS.items():
            color = _measurement_cell_color(field_name, row.get(field_name), maximum)
            if color:
                row_backgrounds[field_name] = color
        if (
            bool(row.get("comment_detected"))
            or bool(row.get("crossed_out_or_side_note_detected"))
        ):
            row_backgrounds["warnings"] = CELL_COLORS["note"]
        backgrounds.append(row_backgrounds)
    return backgrounds


def _highlight_review_row(row: pd.Series) -> list[str]:
    """Highlight each problematic measurement cell with its validation severity."""
    styles = [""] * len(row)
    for field_name, maximum in FIELD_LIMITS.items():
        if field_name not in row.index:
            continue
        value = row.get(field_name)
        color = _measurement_cell_color(field_name, value, maximum)
        if color:
            styles[row.index.get_loc(field_name)] = f"background-color: {color}"

    if (
        bool(row.get("comment_detected"))
        or bool(row.get("crossed_out_or_side_note_detected"))
    ) and "warnings" in row.index:
        styles[row.index.get_loc("warnings")] = (
            f"background-color: {CELL_COLORS['note']}"
        )
    return styles


def _measurement_cell_color(
    field_name: str,
    value: Any,
    maximum: float,
) -> str:
    """Return the requested cell color for one editable measurement value."""
    if _missing(value):
        return CELL_COLORS[
            "missing_weight" if field_name == "Weight" else "missing_required"
        ]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return CELL_COLORS["negative"]
    if not math.isfinite(number) or number < 0:
        return CELL_COLORS["negative"]
    if number > maximum:
        return CELL_COLORS["out_of_range"]
    return ""


def _records_from_dataframe(
    rows: pd.DataFrame,
) -> tuple[list[ExtractedMeasurement], list[str]]:
    """Convert edited cells to models, then validate each source image as one page."""
    records = [
        ExtractedMeasurement(
            source_image=str(row["source_image"]),
            cage_number=_optional_text(row.get("cage_number")),
            mouse_id=_optional_text(row.get("mouse_id")),
            ear_marking=_optional_text(row.get("ear_marking")),
            W=_optional_float(row.get("W")),
            L=_optional_float(row.get("L")),
            Weight=_optional_float(row.get("Weight")),
            comment_detected=bool(row.get("comment_detected", False)),
            crossed_out_or_side_note_detected=bool(
                row.get("crossed_out_or_side_note_detected", False)
            ),
            approved=False,
            warnings=_warnings_from_cell(row.get("warnings")),
        )
        for _, row in rows.iterrows()
    ]

    general_warnings: list[str] = []
    by_image: dict[str, list[ExtractedMeasurement]] = {}
    for record in records:
        by_image.setdefault(record.source_image, []).append(record)
    for image_name, page_records in by_image.items():
        page_result = validate_page(
            [record for record in page_records if not _is_empty_export_slot(record)]
        )
        general_warnings.extend(
            f"{image_name}: {warning}" for warning in page_result.general_warnings
        )
    return records, general_warnings


def _records_to_dataframe(
    records: list[ExtractedMeasurement],
    *,
    correction_contexts: list[Any] | None = None,
    existing_rows: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convert review models to the stable table schema used by Streamlit."""
    rows = []
    for index, record in enumerate(records):
        context = correction_contexts[index] if correction_contexts else None
        existing = (
            existing_rows.iloc[index]
            if existing_rows is not None and index < len(existing_rows)
            else None
        )
        def context_value(column: str, fallback: Any = None) -> Any:
            if existing is not None and column in existing.index:
                return existing[column]
            return fallback

        rows.append(
            {
                "source_image": record.source_image,
                "cage_number": record.cage_number,
                "mouse_id": record.mouse_id,
                "ear_marking": record.ear_marking,
                "W": record.W,
                "L": record.L,
                "Weight": record.Weight,
                "warnings": " | ".join(record.warnings),
                "requires_manual_review": record.requires_manual_review,
                "comment_detected": record.comment_detected,
                "crossed_out_or_side_note_detected": record.crossed_out_or_side_note_detected,
                "page_row": (
                    context.page_row if context is not None else context_value("page_row")
                ),
                **{
                    f"original_{field_name}": (
                        context.original_predictions[field_name]
                        if context is not None
                        else context_value(f"original_{field_name}", getattr(record, field_name))
                    )
                    for field_name in ("W", "L", "Weight")
                },
                **{
                    f"crop_{field_name}": (
                        context.crop_paths[field_name]
                        if context is not None
                        else context_value(f"crop_{field_name}")
                    )
                    for field_name in ("W", "L", "Weight")
                },
            }
        )
    return pd.DataFrame(rows, columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS)


def _restore_internal_columns(
    edited: pd.DataFrame, previous: pd.DataFrame
) -> pd.DataFrame:
    """Restore hidden correction context if Streamlit omits hidden columns."""
    restored = edited.copy()
    for column in INTERNAL_COLUMNS:
        if column not in restored.columns and column in previous.columns:
            restored[column] = previous[column].to_numpy()
    return restored


def _commit_review_rows(
    edited: pd.DataFrame,
) -> tuple[pd.DataFrame, list[ExtractedMeasurement], list[str]]:
    """Validate edited review rows and return the committed export table."""
    records, page_warnings = _records_from_dataframe(edited)
    committed_rows = _records_to_dataframe(records, existing_rows=edited)
    return committed_rows, records, page_warnings


def _has_uncommitted_review_changes(
    draft_rows: pd.DataFrame,
    export_rows: pd.DataFrame,
) -> bool:
    """Return whether the editable draft differs from the export table."""
    normalized_draft = _normalize_review_rows_for_comparison(draft_rows)
    normalized_export = _normalize_review_rows_for_comparison(export_rows)
    return not normalized_draft.equals(normalized_export)


def _normalize_review_rows_for_comparison(rows: pd.DataFrame) -> pd.DataFrame:
    """Compare the stable review schema while treating missing values consistently."""
    normalized = rows.reindex(columns=VISIBLE_COLUMNS + INTERNAL_COLUMNS).copy()
    return normalized.reset_index(drop=True)


def _save_gui_corrections(rows: pd.DataFrame) -> None:
    """Persist changed numeric editor values with their original cell crops."""
    for _, row in rows.iterrows():
        mouse_id = _optional_text(row.get("mouse_id"))
        if mouse_id is None:
            continue
        for field_name in ("W", "L", "Weight"):
            original = _optional_float(row.get(f"original_{field_name}"))
            corrected = _optional_float(row.get(field_name))
            if original == corrected:
                continue
            crop_path = _optional_text(row.get(f"crop_{field_name}"))
            if crop_path is None:
                continue
            key = (
                str(row.get("source_image")),
                str(row.get("page_row")),
                mouse_id,
                field_name,
                original,
                corrected,
                crop_path,
            )
            if key in st.session_state.saved_correction_keys:
                continue
            try:
                saved = save_correction(
                    FieldCorrection(
                        source_image=str(row.get("source_image")),
                        mouse_id=mouse_id,
                        field_name=field_name,
                        original_prediction=original,
                        corrected_value=corrected,
                        crop_path=crop_path,
                    )
                )
                if saved:
                    st.session_state.saved_correction_keys.add(key)
            except (FileNotFoundError, PermissionError, TypeError, ValueError) as exc:
                st.warning(f"Could not save {field_name} correction for mouse {mouse_id}: {exc}")


def _rebase_review_predictions() -> None:
    """Treat current editor values as the new baseline after a learning reset."""
    st.session_state.review_rows = _rebase_prediction_columns(
        st.session_state.review_rows
    )
    st.session_state.draft_review_rows = _rebase_prediction_columns(
        st.session_state.draft_review_rows
    )


def _rebase_prediction_columns(rows: pd.DataFrame) -> pd.DataFrame:
    """Return rows whose current values are treated as correction baselines."""
    rebased = rows.copy()
    for field_name in ("W", "L", "Weight"):
        if field_name in rebased.columns:
            rebased[f"original_{field_name}"] = rebased[field_name]
    return rebased


def _warnings_from_cell(value: Any) -> list[str]:
    """Preserve OCR and validation warnings across editable-table reruns."""
    if _missing(value):
        return []
    return [item.strip() for item in str(value).split(" | ") if item.strip()]


def _render_validation_summary(
    records: list[ExtractedMeasurement], general_warnings: list[str]
) -> None:
    """Show a compact legend and current review counts below the editor."""
    status_counts = {status.value: 0 for status in ValidationStatus}
    for record in records:
        if _is_empty_export_slot(record):
            status_counts[ValidationStatus.OK.value] += 1
            continue
        result = validate_page([record]).row_results[0]
        status_counts[result.status.value] += 1
    st.caption(
        "Highlight legend: red = missing W/L · yellow = missing Weight · "
        "orange = out of range · purple = comment/cross-out/side-note"
    )
    columns = st.columns(4)
    for column, status in zip(columns, ValidationStatus):
        column.metric(status.value, status_counts[status.value])
    for warning in general_warnings:
        st.warning(warning)


def _render_export_approval_controls(
    rows: pd.DataFrame,
    records: list[ExtractedMeasurement],
) -> None:
    """Render explicit export-approval checkboxes outside the editable table."""
    pending_rows: list[tuple[pd.Series, str]] = []
    for (_, row), record in zip(rows.iterrows(), records):
        issues = _row_export_issues(record)
        if issues:
            pending_rows.append((row, ", ".join(issues)))
    if not pending_rows:
        return

    st.markdown("**Export approvals**")
    st.caption(
        "Rows with missing W/L, out-of-range values, or detected notes need one "
        "explicit approval here before export."
    )
    with st.container(horizontal=True):
        if st.button("Approve all", key="approve_all_export_warnings"):
            _set_warning_approval_state([row for row, _ in pending_rows], True)
        if st.button("Disapprove all", key="disapprove_all_export_warnings"):
            _set_warning_approval_state([row for row, _ in pending_rows], False)
    for row, issue_text in pending_rows:
        row_key = _review_row_identity(row)
        checkbox_key = f"warning_approval::{row_key}"
        label = (
            f"Mouse ID {row.get('mouse_id') or '(missing mouse ID)'} "
            f"(cage {row.get('cage_number') or '?'}, row {row.get('page_row') or '?'})"
            f": {issue_text}"
        )
        st.checkbox(label, key=checkbox_key)


def _review_row_identity(row: pd.Series | dict[str, Any]) -> str:
    """Build a stable identity for one reviewed row across export checks."""
    values = [
        str(row.get("source_image") or ""),
        str(row.get("cage_number") or ""),
        str(row.get("page_row") or ""),
        str(row.get("mouse_id") or ""),
    ]
    return "::".join(values)


def _row_export_approved(row: pd.Series | dict[str, Any]) -> bool:
    """Return whether the reviewer explicitly approved this warning row."""
    return bool(st.session_state.get(f"warning_approval::{_review_row_identity(row)}", False))


def _reset_warning_approval_state() -> None:
    """Clear row-level warning approvals after new extraction or a new commit."""
    for key in list(st.session_state.keys()):
        if str(key).startswith("warning_approval::"):
            del st.session_state[key]


def _set_warning_approval_state(
    rows: list[pd.Series] | list[dict[str, Any]],
    approved: bool,
) -> None:
    """Set row-level warning approvals for a batch of displayed export rows."""
    for row in rows:
        st.session_state[f"warning_approval::{_review_row_identity(row)}"] = approved


def _export_reviewed_rows(template_path: Path | None) -> None:
    """Validate every committed row before writing any values to Excel."""
    if template_path is None:
        st.error("Select or upload an Excel template before export.")
        return
    if st.session_state.review_rows.empty:
        st.error("Run extraction before export.")
        return
    try:
        config = Config.load(
            DEFAULT_SETTINGS_PATH, excel_template_path_override=template_path
        )
        config, output_storage_warning = _config_with_writable_output_folder(config)
        review_rows = st.session_state.review_rows
        records, _ = _records_from_dataframe(review_rows)
        export_pairs = [
            (row, record)
            for (_, row), record in zip(review_rows.iterrows(), records)
            if not _is_empty_export_slot(record)
        ]
        for row, record in export_pairs:
            record.approved = _row_export_approved(row)
        export_records = [record for _, record in export_pairs]
        blockers = _unapproved_export_issues(export_records)
        if blockers:
            st.error(
                "Export blocked. Fix the values below or approve each affected "
                "row in the export-approval section."
            )
            for blocker in blockers:
                st.markdown(f"- {blocker}")
            return

        # Clean rows and rows missing only Weight are exportable immediately.
        # Warning rows are exported only after their external approval checkbox is marked.
        for record in export_records:
            record.approved = True
        output_name = f"mouse_monitor_export_{datetime.now():%Y%m%d_%H%M%S_%f}.xlsx"
        result = export_validated_measurements_to_excel(
            template_path,
            output_name,
            export_records,
            config,
            allow_duplicate_measurement_ids=st.session_state.duplicate_override_enabled,
        )
        st.session_state.latest_export = result
        st.success(
            f"Export complete: {result.written_measurements} reviewed row(s) written; "
            f"{result.skipped_measurements} skipped."
        )
        if output_storage_warning:
            st.warning(output_storage_warning)
        for warning in result.warnings:
            st.warning(warning)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        st.error(f"Export failed: {exc}")


def _render_latest_export() -> None:
    """Offer the latest generated workbook for download after export."""
    result = st.session_state.latest_export
    if result is None or not result.output_path.is_file():
        return
    st.download_button(
        "Download exported Excel",
        data=result.output_path.read_bytes(),
        file_name=result.output_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _config_with_writable_output_folder(config: Config) -> tuple[Config, str | None]:
    """Use a temp output folder when the configured project folder is not writable."""
    if _folder_is_writable(config.output_folder):
        return config, None
    fallback_folder = _temporary_runtime_folder("output")
    return (
        replace(config, output_folder=fallback_folder),
        f"data/output is not writable; using temporary folder {fallback_folder}.",
    )


def _folder_is_writable(folder: Path) -> bool:
    """Verify that a folder accepts create/write/delete operations."""
    probe = folder / f".writable_probe_{datetime.now():%Y%m%d_%H%M%S_%f}.tmp"
    try:
        probe.write_bytes(b"probe")
        probe.unlink()
        return True
    except OSError:
        return False


def _optional_float(value: Any) -> float | None:
    """Convert an editable numeric cell while keeping blank distinct from zero."""
    if _missing(value):
        return None
    return float(value)


def _optional_text(value: Any) -> str | None:
    """Convert a table value to optional text."""
    if _missing(value):
        return None
    text = str(value).strip()
    return text or None


def _missing(value: Any) -> bool:
    """Recognize None/NaN without classifying numeric zero as missing."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _outside_range(value: Any, minimum: float, maximum: float) -> bool:
    """Return whether a present numeric editor value falls outside its range."""
    if _missing(value):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return True
    return not math.isfinite(number) or number < minimum or number > maximum


def _unapproved_export_issues(
    records: list[ExtractedMeasurement],
) -> list[str]:
    """List blocking fields for rows that lack a specific warning override."""
    issues: list[str] = []
    for record in records:
        field_issues = _blocking_field_issues(record)
        row_issues = _row_export_issues(record)
        has_fatal_value = any("not a finite number" in issue for issue in field_issues)
        if row_issues and (not record.approved or has_fatal_value):
            mouse_label = record.mouse_id or "(missing mouse ID)"
            issues.append(f"Mouse ID {mouse_label}: {', '.join(row_issues)}")
    return issues


def _row_export_issues(record: ExtractedMeasurement) -> list[str]:
    """Return blocking export issues for one reviewed row."""
    if _is_empty_export_slot(record):
        return []
    field_issues = _blocking_field_issues(record)
    note_issues: list[str] = []
    if record.comment_detected:
        note_issues.append("comment detected")
    if record.crossed_out_or_side_note_detected:
        note_issues.append("crossed-out value or side note detected")
    return [*field_issues, *note_issues]


def _is_empty_export_slot(record: ExtractedMeasurement) -> bool:
    """Return whether a fixed cage slot is intentionally empty and non-exportable."""
    return (
        record.mouse_id is None
        and record.W is None
        and record.L is None
        and record.Weight is None
        and not record.comment_detected
        and not record.crossed_out_or_side_note_detected
        and not record.warnings
    )


def _blocking_field_issues(record: ExtractedMeasurement) -> list[str]:
    """Return only issues that require approval before export."""
    issues: list[str] = []
    for field_name, maximum in FIELD_LIMITS.items():
        value = getattr(record, field_name)
        if value is None:
            if field_name in {"W", "L"}:
                issues.append(f"{field_name} is missing")
            continue
        number = float(value)
        if not math.isfinite(number):
            issues.append(f"{field_name} is not a finite number")
        elif number < 0:
            issues.append(f"{field_name} is negative ({number:.2f})")
        elif number > maximum:
            issues.append(
                f"{field_name} is above {maximum:.2f} ({number:.2f})"
            )
    return issues
