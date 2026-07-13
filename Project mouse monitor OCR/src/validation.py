"""Validation rules for extracted mouse measurements."""

from dataclasses import dataclass
from enum import Enum
import math
from collections.abc import Iterable, Mapping

from .review_model import ExtractedMeasurement


DEFAULT_RANGES: dict[str, tuple[float, float]] = {
    "W": (0.0, 20.0),
    "L": (0.0, 20.0),
    "Weight": (0.0, 40.0),
}
EMPTY_WEIGHT_PAGE_WARNING = "Weight column appears to be empty for this page."


class ValidationStatus(str, Enum):
    """Overall severity for one extracted row."""

    OK = "OK"
    WARNING = "WARNING"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome for one measurement row."""

    measurement: ExtractedMeasurement
    status: ValidationStatus
    warnings: list[str]
    requires_explicit_approval: bool

    @property
    def export_allowed(self) -> bool:
        """Return whether this row can currently be exported."""
        if self.status is ValidationStatus.ERROR:
            return False
        return not self.requires_explicit_approval or self.measurement.approved


@dataclass(frozen=True)
class PageValidationResult:
    """Hold row results and warnings that apply once to the whole image/page."""

    row_results: list[ValidationResult]
    general_warnings: list[str]


def validate_measurement(
    measurement: ExtractedMeasurement,
    valid_ranges: Mapping[str, tuple[float, float]] | None = None,
) -> ValidationResult:
    """Validate one row, preserving zero as a valid non-missing value."""
    ranges = valid_ranges or DEFAULT_RANGES
    measurement.warnings = [
        warning
        for warning in measurement.warnings
        if not _is_generated_validation_warning(warning)
    ]
    warnings: list[str] = []
    status = ValidationStatus.OK
    requires_approval = False

    for field_name in ("W", "L", "Weight"):
        value = getattr(measurement, field_name)
        if value is None:
            if field_name in ("W", "L"):
                warnings.append(f"{field_name} is missing and requires explicit approval.")
                status = _stronger(status, ValidationStatus.REQUIRES_APPROVAL)
                requires_approval = True
            else:
                warnings.append("Weight is missing.")
                status = _stronger(status, ValidationStatus.WARNING)
            continue

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            warnings.append(f"{field_name} must be numeric or missing.")
            status = ValidationStatus.ERROR
            continue
        if not math.isfinite(float(value)):
            warnings.append(f"{field_name} must be a finite number.")
            status = ValidationStatus.ERROR
            continue

        minimum, maximum = ranges[field_name]
        if value < 0:
            warnings.append(f"{field_name} is negative and requires explicit approval.")
            status = _stronger(status, ValidationStatus.REQUIRES_APPROVAL)
            requires_approval = True
        elif value < minimum or value > maximum:
            warnings.append(
                f"{field_name}={value:.2f} is outside the valid range "
                f"{minimum:.2f}-{maximum:.2f} and requires explicit approval."
            )
            status = _stronger(status, ValidationStatus.REQUIRES_APPROVAL)
            requires_approval = True

    if measurement.comment_detected:
        warnings.append("A comment was detected; manual review is required.")
        status = _stronger(status, ValidationStatus.REQUIRES_APPROVAL)
        requires_approval = True
    if measurement.crossed_out_or_side_note_detected:
        warnings.append("A crossed-out value or side note was detected; manual review is required.")
        status = _stronger(status, ValidationStatus.REQUIRES_APPROVAL)
        requires_approval = True

    measurement.requires_manual_review = (
        status in (ValidationStatus.REQUIRES_APPROVAL, ValidationStatus.ERROR)
    )
    for warning in warnings:
        if warning not in measurement.warnings:
            measurement.warnings.append(warning)

    return ValidationResult(
        measurement=measurement,
        status=status,
        warnings=warnings,
        requires_explicit_approval=requires_approval,
    )


def validate_page(
    measurements: Iterable[ExtractedMeasurement],
    valid_ranges: Mapping[str, tuple[float, float]] | None = None,
) -> PageValidationResult:
    """Validate one image/page and emit one warning when every Weight is missing."""
    rows = list(measurements)
    row_results = [validate_measurement(row, valid_ranges) for row in rows]
    general_warnings = (
        [EMPTY_WEIGHT_PAGE_WARNING]
        if rows and all(row.Weight is None for row in rows)
        else []
    )
    return PageValidationResult(row_results, general_warnings)


def _stronger(
    current: ValidationStatus, candidate: ValidationStatus
) -> ValidationStatus:
    """Combine statuses without allowing a weaker issue to hide a stronger one."""
    order = {
        ValidationStatus.OK: 0,
        ValidationStatus.WARNING: 1,
        ValidationStatus.REQUIRES_APPROVAL: 2,
        ValidationStatus.ERROR: 3,
    }
    return candidate if order[candidate] > order[current] else current


def _is_generated_validation_warning(warning: str) -> bool:
    """Identify validator-owned messages so corrected rows do not retain stale warnings."""
    if warning in {
        "Weight is missing.",
        "A comment was detected; manual review is required.",
        "A crossed-out value or side note was detected; manual review is required.",
    }:
        return True
    return any(
        warning.startswith(prefix)
        for prefix in (
            "W is missing and requires explicit approval.",
            "L is missing and requires explicit approval.",
            "W is negative and requires explicit approval.",
            "L is negative and requires explicit approval.",
            "Weight is negative and requires explicit approval.",
            "W=",
            "L=",
            "Weight=",
            "W must be numeric or missing.",
            "L must be numeric or missing.",
            "Weight must be numeric or missing.",
            "W must be a finite number.",
            "L must be a finite number.",
            "Weight must be a finite number.",
        )
    )
