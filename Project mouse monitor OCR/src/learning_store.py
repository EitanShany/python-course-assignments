"""Persist reviewer corrections as labeled data for future handwriting models."""

import csv
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

from .config import PROJECT_ROOT
from .review_model import FieldCorrection


DEFAULT_LEARNING_FOLDER = PROJECT_ROOT / "data" / "learning_data"
CORRECTIONS_FILENAME = "corrections.csv"
PENDING_CORRECTIONS_FILENAME = "corrections_pending.csv"
CSV_FIELDS = (
    "timestamp",
    "source_image",
    "mouse_id",
    "field_name",
    "original_prediction",
    "corrected_value",
    "crop_path",
)
_CURRENT_RUN_CORRECTIONS: list[FieldCorrection] = []


def save_correction(
    record: FieldCorrection,
    folder: Path | str = DEFAULT_LEARNING_FOLDER,
) -> bool:
    """Append one changed, crop-backed correction and return whether it was saved."""
    if record.field_name not in {"W", "L", "Weight"}:
        raise ValueError("field_name must be W, L, or Weight.")
    if _values_equal(record.original_prediction, record.corrected_value):
        return False
    if not record.mouse_id.strip():
        raise ValueError("A mouse ID is required for labeled correction data.")
    if not record.crop_path:
        raise ValueError("A crop image path is required for labeled correction data.")
    crop_path = Path(record.crop_path).resolve()
    if not crop_path.is_file():
        raise FileNotFoundError(f"Correction crop not found: {crop_path}")

    learning_folder = Path(folder)
    learning_folder.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": record.timestamp.isoformat(),
        "source_image": record.source_image,
        "mouse_id": record.mouse_id,
        "field_name": record.field_name,
        "original_prediction": _format_optional_value(record.original_prediction),
        "corrected_value": _format_optional_value(record.corrected_value),
        "crop_path": str(crop_path),
    }
    csv_path = learning_folder / CORRECTIONS_FILENAME
    try:
        _append_correction_row(csv_path, row)
    except PermissionError:
        pending_csv_path = learning_folder / PENDING_CORRECTIONS_FILENAME
        _append_correction_row(pending_csv_path, row)
    _CURRENT_RUN_CORRECTIONS.append(record)
    return True


def load_corrections(
    folder: Path | str = DEFAULT_LEARNING_FOLDER,
) -> list[FieldCorrection]:
    """Load all saved correction metadata from the learning folder."""
    records: list[FieldCorrection] = []
    for csv_path in _existing_correction_csv_paths(folder):
        records.extend(_load_corrections_file(csv_path))
    records.sort(key=lambda record: record.timestamp)
    return records


def consolidate_learning_files(
    folder: Path | str = DEFAULT_LEARNING_FOLDER,
) -> bool:
    """Merge split learning CSV files back into one canonical corrections.csv."""
    learning_folder = Path(folder)
    primary_csv = learning_folder / CORRECTIONS_FILENAME
    pending_csv = learning_folder / PENDING_CORRECTIONS_FILENAME
    primary_exists = primary_csv.is_file()
    pending_exists = pending_csv.is_file()

    if not primary_exists and not pending_exists:
        return False
    if pending_exists and not primary_exists:
        pending_csv.replace(primary_csv)
        return True
    if not pending_exists:
        return False

    merged_records = _deduplicated_corrections(load_corrections(learning_folder))
    temp_csv = learning_folder / f"{CORRECTIONS_FILENAME}.tmp"
    _write_correction_rows(
        temp_csv,
        [_correction_to_row(record) for record in merged_records],
    )
    temp_csv.replace(primary_csv)
    pending_csv.unlink()
    return True


def export_learning_data(
    zip_path: Path | str,
    folder: Path | str = DEFAULT_LEARNING_FOLDER,
) -> Path:
    """Export correction metadata and referenced cell crops into a portable ZIP."""
    destination = Path(zip_path).resolve()
    if destination.suffix.lower() != ".zip":
        raise ValueError("Learning export path must use the .zip extension.")
    if destination.exists():
        raise FileExistsError(f"Learning export already exists: {destination}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Learning export folder not found: {destination.parent}")

    learning_folder = Path(folder)
    corrections = load_corrections(learning_folder)
    manifest: list[dict[str, str]] = []
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for csv_path in _existing_correction_csv_paths(learning_folder):
            archive.write(csv_path, csv_path.name)
        for index, correction in enumerate(corrections, start=1):
            if not correction.crop_path:
                continue
            crop_path = Path(correction.crop_path)
            if not crop_path.is_file():
                continue
            digest = hashlib.sha256(crop_path.read_bytes()).hexdigest()[:12]
            archive_name = (
                f"crops/{index:05d}_{digest}_{crop_path.name}"
            )
            archive.write(crop_path, archive_name)
            manifest.append(
                {
                    "timestamp": correction.timestamp.isoformat(),
                    "mouse_id": correction.mouse_id,
                    "field_name": correction.field_name,
                    "original_crop_path": str(crop_path.resolve()),
                    "archive_crop_path": archive_name,
                }
            )
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
    return destination


def reset_learning_data(folder: Path | str = DEFAULT_LEARNING_FOLDER) -> int:
    """Delete all persisted learning artifacts and clear current-run corrections."""
    learning_folder = Path(folder).resolve()
    removed = 0
    if learning_folder.exists():
        for child in learning_folder.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed += 1
    else:
        learning_folder.mkdir(parents=True)
    _CURRENT_RUN_CORRECTIONS.clear()
    return removed


def reset_learning_for_current_run_only() -> int:
    """Clear only in-memory one-run learning state, preserving the correction CSV."""
    removed = len(_CURRENT_RUN_CORRECTIONS)
    _CURRENT_RUN_CORRECTIONS.clear()
    return removed


def current_run_corrections() -> list[FieldCorrection]:
    """Return a defensive copy of corrections captured during this process run."""
    return list(_CURRENT_RUN_CORRECTIONS)


def _values_equal(left: float | None, right: float | None) -> bool:
    """Compare optional values without treating zero as missing."""
    if left is None or right is None:
        return left is right
    return float(left) == float(right)


def _existing_correction_csv_paths(folder: Path | str) -> list[Path]:
    """Return saved correction CSV files in stable read order."""
    learning_folder = Path(folder)
    csv_paths: list[Path] = []
    for file_name in (CORRECTIONS_FILENAME, PENDING_CORRECTIONS_FILENAME):
        csv_path = learning_folder / file_name
        if csv_path.is_file():
            csv_paths.append(csv_path)
    return csv_paths


def _append_correction_row(csv_path: Path, row: dict[str, str]) -> None:
    """Append one correction row, creating the CSV header when needed."""
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _write_correction_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    """Write a complete correction CSV file with the expected header."""
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _load_corrections_file(csv_path: Path) -> list[FieldCorrection]:
    """Load one correction CSV file and validate its schema."""
    records: list[FieldCorrection] = []
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(CSV_FIELDS):
            raise ValueError(f"Unexpected correction CSV columns in {csv_path}.")
        for line_number, row in enumerate(reader, start=2):
            try:
                from datetime import datetime

                records.append(
                    FieldCorrection(
                        source_image=row["source_image"],
                        mouse_id=row["mouse_id"],
                        field_name=row["field_name"],
                        original_prediction=_parse_optional_value(
                            row["original_prediction"]
                        ),
                        corrected_value=_parse_optional_value(row["corrected_value"]),
                        crop_path=row["crop_path"] or None,
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid correction record at {csv_path}:{line_number}: {exc}"
                ) from exc
    return records


def _deduplicated_corrections(
    records: list[FieldCorrection],
) -> list[FieldCorrection]:
    """Remove exact duplicate correction rows while preserving time order."""
    deduplicated: list[FieldCorrection] = []
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    for record in records:
        key = (
            record.timestamp.isoformat(),
            record.source_image,
            record.mouse_id,
            record.field_name,
            _format_optional_value(record.original_prediction),
            _format_optional_value(record.corrected_value),
            record.crop_path or "",
        )
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(record)
    return deduplicated


def _correction_to_row(record: FieldCorrection) -> dict[str, str]:
    """Serialize one correction model back into the CSV row schema."""
    return {
        "timestamp": record.timestamp.isoformat(),
        "source_image": record.source_image,
        "mouse_id": record.mouse_id,
        "field_name": record.field_name,
        "original_prediction": _format_optional_value(record.original_prediction),
        "corrected_value": _format_optional_value(record.corrected_value),
        "crop_path": record.crop_path or "",
    }


def _format_optional_value(value: float | None) -> str:
    """Serialize an optional label using two decimal places."""
    return "" if value is None else f"{float(value):.2f}"


def _parse_optional_value(value: str) -> float | None:
    """Parse an empty CSV value as missing and numeric text as float."""
    return None if value == "" else float(value)
