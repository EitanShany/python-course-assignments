"""Tests for review and correction data models."""

from datetime import datetime
import unittest

from src.review_model import ExtractedMeasurement, FieldCorrection


class ReviewModelTests(unittest.TestCase):
    """Verify missing values, valid zeroes, and independent warning lists."""

    def test_zero_is_preserved_and_none_means_missing(self) -> None:
        """Keep a real 0.00 distinct from an absent measurement."""
        measurement = ExtractedMeasurement(
            source_image="sheet.jpg",
            mouse_id="42",
            W=0.00,
            L=None,
            Weight=0,
        )

        self.assertEqual(measurement.W, 0.0)
        self.assertIsNone(measurement.L)
        self.assertEqual(measurement.Weight, 0.0)

    def test_warning_lists_are_not_shared(self) -> None:
        """Give every extracted row its own mutable warnings list."""
        first = ExtractedMeasurement(source_image="first.jpg")
        second = ExtractedMeasurement(source_image="second.jpg")
        first.warnings.append("low confidence")

        self.assertEqual(second.warnings, [])

    def test_correction_gets_utc_timestamp(self) -> None:
        """Timestamp new correction records and preserve corrected zero."""
        correction = FieldCorrection(
            source_image="sheet.jpg",
            mouse_id="42",
            field_name="W",
            original_prediction=None,
            corrected_value=0.00,
        )

        self.assertIsInstance(correction.timestamp, datetime)
        self.assertIsNotNone(correction.timestamp.tzinfo)
        self.assertEqual(correction.corrected_value, 0.0)


if __name__ == "__main__":
    unittest.main()
