"""Tests for row and page validation rules."""

import unittest

from src.review_model import ExtractedMeasurement
from src.validation import (
    EMPTY_WEIGHT_PAGE_WARNING,
    ValidationStatus,
    validate_measurement,
    validate_page,
)


class ValidationTests(unittest.TestCase):
    """Verify warning severity and explicit export approval behavior."""

    def test_zero_values_are_valid(self) -> None:
        """Accept 0.00 for all three measurements."""
        row = ExtractedMeasurement(source_image="page.jpg", W=0, L=0, Weight=0)

        result = validate_measurement(row)

        self.assertEqual(result.status, ValidationStatus.OK)
        self.assertTrue(result.export_allowed)
        self.assertFalse(row.requires_manual_review)

    def test_missing_w_requires_explicit_approval(self) -> None:
        """Block a missing W until the reviewer approves the row."""
        row = ExtractedMeasurement(source_image="page.jpg", W=None, L=2, Weight=20)
        result = validate_measurement(row)

        self.assertEqual(result.status, ValidationStatus.REQUIRES_APPROVAL)
        self.assertFalse(result.export_allowed)
        row.approved = True
        self.assertTrue(result.export_allowed)

    def test_missing_weight_warns_but_does_not_block(self) -> None:
        """Keep row-level missing Weight non-blocking."""
        row = ExtractedMeasurement(source_image="page.jpg", W=2, L=3, Weight=None)

        result = validate_measurement(row)

        self.assertEqual(result.status, ValidationStatus.WARNING)
        self.assertTrue(result.export_allowed)

    def test_negative_and_out_of_range_values_require_approval(self) -> None:
        """Flag negative and excessive measurements for explicit review."""
        row = ExtractedMeasurement(source_image="page.jpg", W=-1, L=21, Weight=41)

        result = validate_measurement(row)

        self.assertEqual(result.status, ValidationStatus.REQUIRES_APPROVAL)
        self.assertTrue(result.requires_explicit_approval)

    def test_comment_prevents_clean_status_and_auto_approval(self) -> None:
        """Route comments and side notes through manual review."""
        row = ExtractedMeasurement(
            source_image="page.jpg", W=1, L=2, Weight=3, comment_detected=True
        )

        result = validate_measurement(row)

        self.assertEqual(result.status, ValidationStatus.REQUIRES_APPROVAL)
        self.assertTrue(row.requires_manual_review)
        self.assertFalse(row.approved)

    def test_empty_weight_page_warning_is_emitted_once(self) -> None:
        """Create one general warning when the whole page lacks Weight."""
        rows = [
            ExtractedMeasurement(source_image="page.jpg", W=1, L=2),
            ExtractedMeasurement(source_image="page.jpg", W=3, L=4),
        ]

        result = validate_page(rows)

        self.assertEqual(result.general_warnings, [EMPTY_WEIGHT_PAGE_WARNING])
        self.assertEqual(len(result.row_results), 2)

    def test_corrected_value_removes_stale_validation_warning(self) -> None:
        """Refresh user messages after a missing value is manually supplied."""
        row = ExtractedMeasurement(source_image="page.jpg", W=None, L=2, Weight=3)
        validate_measurement(row)
        self.assertTrue(any("W is missing" in warning for warning in row.warnings))

        row.W = 1.5
        result = validate_measurement(row)

        self.assertEqual(result.status, ValidationStatus.OK)
        self.assertFalse(any("W is missing" in warning for warning in row.warnings))


if __name__ == "__main__":
    unittest.main()
