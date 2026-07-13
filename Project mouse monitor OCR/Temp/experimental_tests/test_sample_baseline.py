"""Tests for validating labels before sample-based learning."""

import pytest

from sample_baseline import _optional_number


pytestmark = pytest.mark.full


def test_learning_label_validation_preserves_zero_and_empty() -> None:
    """Accept valid zero and blank labels without conflating them."""
    assert _optional_number(0, "L") == 0.0
    assert _optional_number(None, "Weight") is None


def test_learning_label_validation_rejects_out_of_range_value() -> None:
    """Stop malformed workbook values before they reach correction storage."""
    with pytest.raises(ValueError, match="Invalid L learning value 842.00"):
        _optional_number(842, "L")
