"""Internal data models for OCR predictions and human corrections."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


MeasurementValue = float | None


@dataclass
class ExtractedMeasurement:
    """Represent one extracted mouse row throughout the review workflow."""

    source_image: str
    cage_number: str | None = None
    mouse_id: str | None = None
    ear_marking: str | None = None
    W: MeasurementValue = None
    L: MeasurementValue = None
    Weight: MeasurementValue = None
    comment_detected: bool = False
    crossed_out_or_side_note_detected: bool = False
    confidence_W: float | None = None
    confidence_L: float | None = None
    confidence_Weight: float | None = None
    requires_manual_review: bool = True
    warnings: list[str] = field(default_factory=list)
    approved: bool = False

    def __post_init__(self) -> None:
        """Validate measurement and warning types without treating zero as missing."""
        for field_name in ("W", "L", "Weight"):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                raise TypeError(f"{field_name} must be a float or None.")
            if value is not None:
                setattr(self, field_name, float(value))

        if not isinstance(self.warnings, list) or not all(
            isinstance(warning, str) for warning in self.warnings
        ):
            raise TypeError("warnings must be a list of strings.")


@dataclass
class FieldCorrection:
    """Record a reviewer correction for one predicted measurement field."""

    source_image: str
    mouse_id: str
    field_name: str
    original_prediction: MeasurementValue
    corrected_value: MeasurementValue
    crop_path: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate correction values while retaining valid zero values."""
        for field_name in ("original_prediction", "corrected_value"):
            value = getattr(self, field_name)
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                raise TypeError(f"{field_name} must be a float or None.")
            if value is not None:
                setattr(self, field_name, float(value))

        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime.")
