"""Export approved measurements into a new copy of the Excel template."""

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterable

from .config import Config
from .excel_template import (
    build_mouse_id_mapping,
    load_template,
    normalize_mouse_id,
)
from .review_model import ExtractedMeasurement


class DuplicateMeasurementIDError(ValueError):
    """Raised when imported measurements contain the same mouse more than once."""


@dataclass(frozen=True)
class ExportResult:
    """Summarize a completed Excel export."""

    output_path: Path
    written_measurements: int
    skipped_measurements: int
    warnings: list[str]


def export_validated_measurements_to_excel(
    template_path: Path | str,
    output_path: Path | str,
    measurements: Iterable[ExtractedMeasurement],
    config: Config,
    *,
    allow_duplicate_measurement_ids: bool = False,
) -> ExportResult:
    """Write approved values to K/L/M in a new workbook and preserve all other cells.

    When duplicate override is enabled, only the first occurrence of each mouse
    ID is considered. This explicit switch is intended for a future GUI flow.
    """
    template = Path(template_path).resolve()
    destination = _resolve_output_path(output_path, config)
    _validate_export_paths(template, destination, config)

    records = list(measurements)
    duplicate_ids = _find_duplicate_ids(records)
    if duplicate_ids and not allow_duplicate_measurement_ids:
        joined = ", ".join(sorted(duplicate_ids))
        raise DuplicateMeasurementIDError(
            f"Duplicate mouse IDs in measurements: {joined}. Export was stopped."
        )

    workbook = load_template(template)
    warnings: list[str] = []
    written = 0
    skipped = 0
    seen_ids: set[str] = set()
    try:
        metadata = build_mouse_id_mapping(
            workbook,
            sheet_name=config.sheet_name,
            mouse_id_column=config.mouse_id_column,
            first_data_row=config.mouse_id_start_row,
        )
        worksheet = workbook[config.sheet_name]

        for record in records:
            mouse_id = normalize_mouse_id(record.mouse_id)
            if not record.approved:
                skipped += 1
                continue
            if mouse_id is None:
                warnings.append(
                    f"Approved measurement from '{record.source_image}' has no mouse ID and was skipped."
                )
                skipped += 1
                continue

            if mouse_id in seen_ids:
                warnings.append(
                    f"Additional approved measurement for mouse ID '{mouse_id}' was skipped "
                    "by duplicate override."
                )
                skipped += 1
                continue

            row_number = metadata.mouse_id_to_row.get(mouse_id)
            if row_number is None:
                warnings.append(
                    f"Mouse ID '{mouse_id}' was not found in the Excel template and was skipped."
                )
                skipped += 1
                continue

            seen_ids.add(mouse_id)

            for field_name in ("W", "L", "Weight"):
                value = getattr(record, field_name)
                if value is None:
                    continue
                cell = worksheet[f"{config.output_columns[field_name]}{row_number}"]
                cell.value = float(value)
                cell.number_format = config.excel_number_format
            written += 1

        workbook.save(destination)
    finally:
        workbook.close()

    return ExportResult(
        output_path=destination,
        written_measurements=written,
        skipped_measurements=skipped,
        warnings=warnings,
    )


def _find_duplicate_ids(measurements: list[ExtractedMeasurement]) -> set[str]:
    """Return normalized, non-empty mouse IDs that occur more than once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in measurements:
        mouse_id = normalize_mouse_id(record.mouse_id)
        if mouse_id is None:
            continue
        if mouse_id in seen:
            duplicates.add(mouse_id)
        seen.add(mouse_id)
    return duplicates


def _resolve_output_path(output_path: Path | str, config: Config) -> Path:
    """Resolve a filename inside the configured output folder."""
    candidate = Path(output_path)
    if not candidate.is_absolute():
        candidate = (
            config.output_folder / candidate
            if candidate.parent == Path(".")
            else config.project_root / candidate
        )
    return candidate.resolve()


def _validate_export_paths(template: Path, output: Path, config: Config) -> None:
    """Reject template overwrite, existing output, and paths outside data/output."""
    if not template.is_file():
        raise FileNotFoundError(f"Excel template not found: {template}")
    if output == template:
        raise ValueError("Output path must not overwrite the original Excel template.")
    if output.suffix.lower() != ".xlsx":
        raise ValueError("Output file must use the .xlsx extension.")
    if not output.is_relative_to(config.output_folder.resolve()):
        raise ValueError(
            f"Output file must be inside the configured output folder: {config.output_folder}"
        )
    if output.exists():
        raise FileExistsError(f"Output file already exists; choose a new name: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Output folder not found: {output.parent}")
