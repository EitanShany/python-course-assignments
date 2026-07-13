"""Benchmark pretrained PaddleOCR on the verified two-day cell crops."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re

from src.config import PROJECT_ROOT
from src.paddle_handwriting_ocr import PaddleHandwritingRecognizer


NUMERIC_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
FIELD_MAXIMUMS = {"W": 20.0, "L": 20.0, "Weight": 40.0}
MINIMUM_CONFIDENCE = 0.55


@dataclass(frozen=True)
class BenchmarkSummary:
    """Hold the main accuracy and blank-cell safety metrics."""

    report_path: Path
    labeled_cells: int
    exact_matches: int
    blank_cells: int
    blank_false_positives: int
    rejected_predictions: int


def run_benchmark() -> BenchmarkSummary:
    """Evaluate one frozen pretrained model without changing learning data."""
    source_report = _latest_sample_report()
    output_path = _new_report_path()
    recognizer = PaddleHandwritingRecognizer()
    output_rows: list[dict[str, str]] = []
    labeled_cells = 0
    exact_matches = 0
    blank_cells = 0
    blank_false_positives = 0
    rejected_predictions = 0

    with source_report.open(newline="", encoding="utf-8") as report_file:
        rows = csv.DictReader(report_file)
        required = {
            "sample_set",
            "workbook_sheet",
            "source_image",
            "mouse_id",
            "field_name",
            "expected_value",
            "crop_path",
        }
        if rows.fieldnames is None or not required.issubset(rows.fieldnames):
            raise ValueError("Sample report is missing required benchmark columns.")

        for row in rows:
            field_name = row["field_name"]
            if field_name not in FIELD_MAXIMUMS:
                raise ValueError(f"Unexpected benchmark field: {field_name!r}")
            expected = _optional_number(row["expected_value"])
            if expected is not None and not 0.0 <= expected <= FIELD_MAXIMUMS[field_name]:
                continue
            crop_path = Path(row["crop_path"])
            text, confidence, diagnostics = recognizer.recognize_number(
                crop_path,
                field_name,
            )
            candidate = _numeric_candidate(text)
            accepted = (
                candidate is not None
                and confidence >= MINIMUM_CONFIDENCE
                and 0.0 <= candidate <= FIELD_MAXIMUMS[field_name]
            )
            predicted = candidate if accepted else None

            if expected is None:
                blank_cells += 1
                if predicted is not None:
                    blank_false_positives += 1
            else:
                labeled_cells += 1
                if predicted is not None and round(predicted, 2) == round(expected, 2):
                    exact_matches += 1
            if text and predicted is None:
                rejected_predictions += 1

            output_rows.append(
                {
                    "sample_set": row["sample_set"],
                    "workbook_sheet": row["workbook_sheet"],
                    "source_image": row["source_image"],
                    "mouse_id": row["mouse_id"],
                    "field_name": field_name,
                    "expected_value": _format_number(expected),
                    "paddle_text": text,
                    "paddle_value": _format_number(predicted),
                    "confidence": f"{confidence:.4f}",
                    "exact_match": str(
                        expected is not None
                        and predicted is not None
                        and round(predicted, 2) == round(expected, 2)
                    ),
                    "backend": str(diagnostics.get("backend", "")),
                    "crop_path": str(crop_path),
                }
            )

    _write_report(output_path, output_rows)
    return BenchmarkSummary(
        report_path=output_path,
        labeled_cells=labeled_cells,
        exact_matches=exact_matches,
        blank_cells=blank_cells,
        blank_false_positives=blank_false_positives,
        rejected_predictions=rejected_predictions,
    )


def _latest_sample_report() -> Path:
    """Select the newest local sample report and reject paths outside the project."""
    reports = sorted(
        (PROJECT_ROOT / "data" / "output").glob("sample_baseline_report_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not reports:
        raise FileNotFoundError("No sample baseline report is available for benchmarking.")
    report = reports[0].resolve()
    if not report.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("Benchmark report must be inside the project folder.")
    return report


def _new_report_path() -> Path:
    """Create a timestamped destination without overwriting an earlier benchmark."""
    folder = PROJECT_ROOT / "data" / "output"
    for attempt in range(100):
        suffix = f"_{attempt:02d}" if attempt else ""
        path = folder / f"paddle_benchmark_{datetime.now():%Y%m%d_%H%M%S_%f}{suffix}.csv"
        if not path.exists():
            return path
    raise FileExistsError(f"Could not create a benchmark report in {folder}")


def _numeric_candidate(text: str) -> float | None:
    """Parse only an unambiguous decimal number; never guess missing punctuation."""
    cleaned = re.sub(r"\s+", "", str(text or "")).replace(",", ".")
    if not NUMERIC_PATTERN.fullmatch(cleaned):
        return None
    try:
        value = Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return float(value)


def _optional_number(text: str) -> float | None:
    """Read a verified report value while preserving an intentional blank."""
    if not str(text or "").strip():
        return None
    candidate = _numeric_candidate(text)
    if candidate is None:
        raise ValueError(f"Invalid expected benchmark value: {text!r}")
    return candidate


def _format_number(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def _write_report(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError("PaddleOCR benchmark produced no rows.")
    with path.open("x", newline="", encoding="utf-8") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    summary = run_benchmark()
    accuracy = (
        summary.exact_matches / summary.labeled_cells
        if summary.labeled_cells
        else 0.0
    )
    print(f"Report: {summary.report_path}")
    print(
        f"Exact labeled-cell accuracy: {summary.exact_matches}/"
        f"{summary.labeled_cells} ({accuracy:.1%})"
    )
    print(
        "Blank-cell false positives: "
        f"{summary.blank_false_positives}/{summary.blank_cells}"
    )
    print(f"Rejected non-empty predictions: {summary.rejected_predictions}")


if __name__ == "__main__":
    main()
