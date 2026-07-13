"""Tests for conservative PaddleOCR benchmark parsing."""

from benchmark_paddle_ocr import _numeric_candidate, _optional_number


def test_numeric_candidate_accepts_dot_or_comma_without_guessing() -> None:
    assert _numeric_candidate(" 3.20 ") == 3.2
    assert _numeric_candidate("3,20") == 3.2
    assert _numeric_candidate("3O20") is None
    assert _numeric_candidate("") is None


def test_optional_number_keeps_blank_distinct_from_zero() -> None:
    assert _optional_number("") is None
    assert _optional_number("0.00") == 0.0
