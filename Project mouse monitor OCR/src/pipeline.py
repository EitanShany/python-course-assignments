"""Connect image loading, cell detection, OCR, review models, and validation."""
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .excel_template import normalize_mouse_id
from .image_loader import PreprocessedImage
from .ocr_engine import OCREngine, OCRResult
from .review_model import ExtractedMeasurement
from .table_detection import (
    DEFAULT_CROPS_FOLDER,
    TableDetectionResult,
    detect_table,
)
from .validation import validate_page


@dataclass(frozen=True)
class ExtractionPipelineResult:
    """Hold OCR measurements, table diagnostics, and page-level warnings."""

    measurements: list[ExtractedMeasurement]
    table_results: list[TableDetectionResult]
    general_warnings: list[str]
    system_warnings: list[str]
    correction_contexts: list["MeasurementCorrectionContext"]


@dataclass(frozen=True)
class MeasurementCorrectionContext:
    """Retain model predictions and crop paths aligned with one review row."""

    source_image: str
    page_row: int
    original_predictions: dict[str, float | None]
    crop_paths: dict[str, str]


class DuplicateExtractedMouseIDError(ValueError):
    """Stop default processing while retaining results for explicit GUI override."""

    def __init__(
        self,
        duplicate_sources: dict[str, list[str]],
        result: ExtractionPipelineResult,
    ) -> None:
        self.duplicate_sources = duplicate_sources
        self.result = result
        details = "; ".join(
            f"{mouse_id}: {', '.join(sources)}"
            for mouse_id, sources in sorted(duplicate_sources.items())
        )
        super().__init__(
            f"Duplicate mouse IDs detected across extracted rows: {details}. "
            "Processing stopped until explicit override."
        )


@dataclass(frozen=True)
class _PendingPageRow:
    """Keep OCR results for one visible row until page-level ID sequence inference runs."""

    page_row: int
    cage_number: str
    empty_slot: bool
    mouse_result: OCRResult
    numeric_results: dict[str, OCRResult]
    parsed_measurements: dict[str, float | None]
    comment_detected: bool
    crossed_out: bool


def extract_measurements_from_images(
    images: Iterable[PreprocessedImage],
    *,
    ocr_engine: OCREngine | None = None,
    crops_folder: Path | str = DEFAULT_CROPS_FOLDER,
    debug_table: bool = False,
    allow_duplicate_mouse_ids: bool = False,
) -> ExtractionPipelineResult:
    """Run cell-by-cell OCR for every uploaded page and validate extracted rows."""
    engine = ocr_engine or OCREngine()
    measurements: list[ExtractedMeasurement] = []
    table_results: list[TableDetectionResult] = []
    general_warnings: list[str] = []
    system_warnings: set[str] = set()
    correction_contexts: list[MeasurementCorrectionContext] = []

    for image_index, image in enumerate(images):
        table = detect_table(
            image.perspective_corrected,
            source_image=image.metadata.source_name,
            crops_folder=crops_folder,
            debug=debug_table,
        )
        table_results.append(table)
        page_measurements: list[ExtractedMeasurement] = []
        pending_rows: list[_PendingPageRow] = []
        for page_row in range(1, 31):
            cells = table.cells_for_row(page_row)
            if not cells:
                continue
            mouse_result = engine.read_printed_mouse_id(cells["mouse_id"].crop_path)
            numeric_results = {
                field_name: engine.read_number(cells[field_name].crop_path, field_name)
                for field_name in ("W", "L", "Weight")
            }
            parsed_measurements = {
                field_name: _accepted_measurement_value(
                    numeric_results[field_name].parsed_value,
                    field_name,
                )
                for field_name in ("W", "L", "Weight")
            }
            visible_content = any(
                engine.has_visible_content(cells[field_name].crop_path)
                for field_name in ("mouse_id", "W", "L")
            )
            _collect_backend_warning(mouse_result, system_warnings)
            for result in numeric_results.values():
                _collect_backend_warning(result, system_warnings)

            empty_slot = not visible_content and not mouse_result.text
            if empty_slot:
                comment_detected = False
                crossed_out = False
            else:
                comment_detected = engine.detect_comment_or_side_note(
                    cells["Comment"].crop_path
                )
                crossed_out = any(
                    engine.detect_cross_out(cells[field_name].crop_path)
                    for field_name in ("W", "L", "Weight", "Comment")
                )

            row_region = cells["mouse_id"]
            pending_rows.append(
                _PendingPageRow(
                    page_row=page_row,
                    cage_number=str(image_index * 6 + row_region.cage_number),
                    empty_slot=empty_slot,
                    mouse_result=mouse_result,
                    numeric_results=numeric_results,
                    parsed_measurements=parsed_measurements,
                    comment_detected=comment_detected,
                    crossed_out=crossed_out,
                )
            )
            correction_contexts.append(
                MeasurementCorrectionContext(
                    source_image=image.metadata.source_name,
                    page_row=page_row,
                    original_predictions={
                        field_name: parsed_measurements[field_name]
                        for field_name in ("W", "L", "Weight")
                    },
                    crop_paths={
                        field_name: str(cells[field_name].crop_path)
                        for field_name in ("W", "L", "Weight")
                    },
                )
            )

        for pending in pending_rows:
            mouse_id = pending.mouse_result.text if pending.mouse_result.parsed_value is not None else None
            warnings: list[str] = []
            if pending.empty_slot:
                requires_manual_review = False
            else:
                requires_manual_review = True
            if pending.mouse_result.text and mouse_id is None:
                warnings.append(
                    f"Mouse ID OCR candidate '{pending.mouse_result.text}' was not confident enough."
                )
            if not mouse_id and not pending.empty_slot:
                warnings.append("Mouse ID is missing or unreadable.")
            for field_name, result in pending.numeric_results.items():
                if result.text and result.parsed_value is None:
                    warnings.append(
                        f"Low-confidence {field_name} OCR candidate: '{result.text}'."
                    )
            page_measurements.append(
                ExtractedMeasurement(
                    source_image=image.metadata.source_name,
                    cage_number=pending.cage_number,
                    mouse_id=mouse_id,
                    ear_marking=None,
                    W=pending.parsed_measurements["W"],
                    L=pending.parsed_measurements["L"],
                    Weight=pending.parsed_measurements["Weight"],
                    comment_detected=pending.comment_detected,
                    crossed_out_or_side_note_detected=pending.crossed_out,
                    confidence_W=pending.numeric_results["W"].confidence,
                    confidence_L=pending.numeric_results["L"].confidence,
                    confidence_Weight=pending.numeric_results["Weight"].confidence,
                    requires_manual_review=requires_manual_review,
                    warnings=warnings,
                    approved=False,
                )
            )

        validation = validate_page(
            [
                measurement
                for measurement in page_measurements
                if not _is_empty_measurement_slot(measurement)
            ]
        )
        general_warnings.extend(
            f"{image.metadata.source_name}: {warning}"
            for warning in validation.general_warnings
        )
        measurements.extend(page_measurements)

    result = ExtractionPipelineResult(
        measurements=measurements,
        table_results=table_results,
        general_warnings=general_warnings,
        system_warnings=sorted(system_warnings),
        correction_contexts=correction_contexts,
    )
    duplicates = _duplicate_mouse_sources(measurements)
    if duplicates and not allow_duplicate_mouse_ids:
        raise DuplicateExtractedMouseIDError(duplicates, result)
    return result


def _duplicate_mouse_sources(
    measurements: list[ExtractedMeasurement],
) -> dict[str, list[str]]:
    """Find duplicate normalized IDs and report each source image and cage."""
    occurrences: dict[str, list[str]] = {}
    for measurement in measurements:
        mouse_id = normalize_mouse_id(measurement.mouse_id)
        if mouse_id is None:
            continue
        location = f"{measurement.source_image} (cage {measurement.cage_number})"
        occurrences.setdefault(mouse_id, []).append(location)
    return {
        mouse_id: sources
        for mouse_id, sources in occurrences.items()
        if len(sources) > 1
    }


def _collect_backend_warning(result: OCRResult, warnings: set[str]) -> None:
    """Collect one copy of optional-backend failures for display in the GUI."""
    if isinstance(result.raw_output, dict) and result.raw_output.get("error"):
        warnings.add(str(result.raw_output["error"]))


def _is_empty_measurement_slot(measurement: ExtractedMeasurement) -> bool:
    """Return whether this fixed cage slot has no detected mouse data."""
    return (
        measurement.mouse_id is None
        and measurement.W is None
        and measurement.L is None
        and measurement.Weight is None
        and not measurement.comment_detected
        and not measurement.crossed_out_or_side_note_detected
        and not measurement.warnings
    )


def _accepted_measurement_value(
    value: float | None,
    field_name: str,
) -> float | None:
    """Keep only biologically plausible OCR measurements in the review table."""
    if value is None:
        return None
    maximum = 40.0 if field_name == "Weight" else 20.0
    return value if 0.0 <= value <= maximum else None
