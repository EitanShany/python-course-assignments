"""Tests for pluggable cell OCR normalization and confidence behavior."""

from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from src.ocr_engine import OCREngine, _prepare_mouse_id_variants


class FakeBackend:
    """Deterministic backend used without an external OCR installation."""

    def __init__(self, text: str, confidence: float) -> None:
        self.text = text
        self.confidence = confidence

    def recognize(
        self,
        image: np.ndarray,
        *,
        character_whitelist: str | None,
        page_segmentation_mode: int,
    ) -> tuple[str, float, dict[str, object]]:
        """Return the configured baseline prediction."""
        return self.text, self.confidence, {
            "whitelist": character_whitelist,
            "psm": page_segmentation_mode,
        }


class SequenceBackend:
    """Return a different OCR prediction on each call for variant-selection tests."""

    def __init__(self, responses: list[tuple[str, float]]) -> None:
        self.responses = list(responses)
        self.call_count = 0

    def recognize(
        self,
        image: np.ndarray,
        *,
        character_whitelist: str | None,
        page_segmentation_mode: int,
    ) -> tuple[str, float, dict[str, object]]:
        """Yield the next configured response while recording how many variants ran."""
        index = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        text, confidence = self.responses[index]
        return text, confidence, {
            "call_count": self.call_count,
            "whitelist": character_whitelist,
            "psm": page_segmentation_mode,
        }


class FakeHandwritingRecognizer:
    """Deterministic personal handwriting recognizer for fallback tests."""

    def __init__(self, text: str, confidence: float) -> None:
        self.text = text
        self.confidence = confidence

    def recognize_number(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> tuple[str, float, dict[str, object]]:
        """Return a personal handwriting candidate."""
        return self.text, self.confidence, {
            "backend": "personal_handwriting",
            "field_name": field_name,
            "crop": str(crop_image_path),
        }


class FakePaddleRecognizer:
    """Deterministic Paddle-style recognizer for fallback-order tests."""

    def __init__(self, text: str, confidence: float) -> None:
        self.text = text
        self.confidence = confidence

    def recognize_number(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> tuple[str, float, dict[str, object]]:
        """Return a numeric handwriting candidate from the optional Paddle path."""
        return self.text, self.confidence, {
            "backend": "paddleocr",
            "field_name": field_name,
            "crop": str(crop_image_path),
        }


class OCREngineTests(unittest.TestCase):
    """Verify numeric parsing, zero handling, confidence, and simple marks."""

    def setUp(self) -> None:
        """Create marked and blank crops for backend-independent tests."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.crop = Path(self.temporary.name) / "cell.png"
        marked = np.full((60, 160, 3), 255, dtype=np.uint8)
        cv2.putText(
            marked,
            "12",
            (35, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(self.crop), marked)
        self.blank_crop = Path(self.temporary.name) / "blank.png"
        cv2.imwrite(
            str(self.blank_crop),
            np.full((60, 160, 3), 255, dtype=np.uint8),
        )

    def test_decimal_comma_and_zero_are_valid(self) -> None:
        """Normalize 0,00 to the valid value and text 0.00."""
        result = OCREngine(
            FakeBackend(" 0,00 ", 0.95),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "W")

        self.assertEqual(result.text, "0.00")
        self.assertEqual(result.parsed_value, 0.0)
        self.assertEqual(result.confidence, 0.95)

    def test_empty_text_is_missing_not_zero(self) -> None:
        """Keep an empty cell absent even if a backend reports confidence."""
        result = OCREngine(
            FakeBackend("", 0.90),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "L")

        self.assertEqual(result.text, "")
        self.assertIsNone(result.parsed_value)
        self.assertLessEqual(result.confidence, 0.10)

    def test_blank_cell_stays_empty_even_if_recognizers_suggest_a_value(self) -> None:
        """Reject OCR guesses when the source cell contains no meaningful ink."""
        result = OCREngine(
            FakeBackend("8.25", 0.99),
            handwriting_recognizer=FakeHandwritingRecognizer("7.50", 0.99),
        ).read_number(self.blank_crop, "W")

        self.assertEqual(result.text, "")
        self.assertIsNone(result.parsed_value)
        self.assertEqual(result.raw_output, {"empty_cell": True})

    def test_table_borders_do_not_make_an_empty_cell_visible(self) -> None:
        """Ignore long grid lines in an otherwise empty measurement cell."""
        bordered = np.full((60, 160, 3), 220, dtype=np.uint8)
        cv2.line(bordered, (0, 8), (159, 8), (30, 30, 30), 2)
        cv2.line(bordered, (25, 0), (25, 59), (30, 30, 30), 2)
        path = Path(self.temporary.name) / "bordered.png"
        cv2.imwrite(str(path), bordered)

        engine = OCREngine(FakeBackend("9.99", 0.99))

        self.assertFalse(engine.has_visible_content(path))
        self.assertIsNone(engine.read_number(path, "Weight").parsed_value)
        self.assertFalse(engine.detect_cross_out(path))

    def test_faint_thin_stroke_is_not_discarded_as_empty(self) -> None:
        """Keep a very light, narrow digit candidate visible for OCR review."""
        faint = np.full((60, 160, 3), 255, dtype=np.uint8)
        cv2.line(faint, (80, 19), (80, 34), (120, 120, 120), 1)
        cv2.line(faint, (77, 22), (83, 22), (120, 120, 120), 1)
        path = Path(self.temporary.name) / "faint.png"
        cv2.imwrite(str(path), faint)

        result = OCREngine(
            FakeBackend("1.20", 0.98),
            enable_personal_handwriting=False,
        ).read_number(path, "W")

        self.assertEqual(result.text, "1.20")
        self.assertEqual(result.parsed_value, 1.2)

    def test_small_dust_dot_stays_empty(self) -> None:
        """Do not promote tiny isolated dust into a numeric cell value."""
        dusty = np.full((60, 160, 3), 255, dtype=np.uint8)
        cv2.rectangle(dusty, (80, 24), (82, 26), (120, 120, 120), -1)
        path = Path(self.temporary.name) / "dusty.png"
        cv2.imwrite(str(path), dusty)

        result = OCREngine(
            FakeBackend("7.50", 0.99),
            enable_personal_handwriting=False,
        ).read_number(path, "W")

        self.assertEqual(result.text, "")
        self.assertIsNone(result.parsed_value)
        self.assertEqual(result.raw_output, {"empty_cell": True})

    def test_low_confidence_value_is_not_accepted(self) -> None:
        """Retain candidate text for review but do not parse uncertain OCR."""
        result = OCREngine(
            FakeBackend("12.345", 0.30),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "Weight")

        self.assertEqual(result.text, "12.35")
        self.assertIsNone(result.parsed_value)
        self.assertEqual(result.confidence, 0.30)

    def test_non_numeric_output_is_rejected(self) -> None:
        """Reject units and letters instead of extracting a misleading substring."""
        result = OCREngine(
            FakeBackend("12kg", 0.99),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "Weight")

        self.assertIsNone(result.parsed_value)
        self.assertLessEqual(result.confidence, 0.25)

    def test_missing_decimal_is_restored_for_w_and_l_when_range_is_clear(self) -> None:
        """Interpret a digit-only W/L OCR token cautiously when the decimal is missing."""
        result = OCREngine(
            FakeBackend("318", 0.93),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "W")

        self.assertEqual(result.text, "3.18")
        self.assertEqual(result.parsed_value, 3.18)
        self.assertTrue(result.raw_output["inferred_decimal"])

    def test_missing_decimal_is_restored_for_weight_when_range_is_clear(self) -> None:
        """Interpret a digit-only Weight OCR token cautiously when the decimal is missing."""
        result = OCREngine(
            FakeBackend("184", 0.94),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "Weight")

        self.assertEqual(result.text, "18.40")
        self.assertEqual(result.parsed_value, 18.4)
        self.assertTrue(result.raw_output["inferred_decimal"])

    def test_implausible_field_value_is_not_filled(self) -> None:
        """Reject OCR values outside the configured biological review range."""
        result = OCREngine(
            FakeBackend("9118", 0.99),
            enable_personal_handwriting=False,
        ).read_number(self.crop, "Weight")

        self.assertEqual(result.text, "9118.00")
        self.assertIsNone(result.parsed_value)
        self.assertLessEqual(result.confidence, 0.25)

    def test_multiple_variants_can_recover_a_valid_numeric_result(self) -> None:
        """Keep the best valid result when one preprocessing variant fails and another works."""
        backend = SequenceBackend([("12kg", 0.95), ("12.30", 0.72), ("", 0.0)])

        result = OCREngine(
            backend,
            enable_personal_handwriting=False,
        ).read_number(self.crop, "Weight")

        self.assertGreaterEqual(backend.call_count, 2)
        self.assertEqual(result.text, "12.30")
        self.assertEqual(result.parsed_value, 12.3)
        self.assertEqual(result.raw_output["variant"], "adaptive")

    def test_personal_handwriting_fallback_accepts_corrected_style(self) -> None:
        """Use the local personal recognizer when baseline OCR is missing."""
        result = OCREngine(
            FakeBackend("", 0.0),
            handwriting_recognizer=FakeHandwritingRecognizer("7.50", 0.92),
        ).read_number(self.crop, "W")

        self.assertEqual(result.text, "7.50")
        self.assertEqual(result.parsed_value, 7.5)
        self.assertEqual(result.raw_output["backend"], "personal_handwriting")

    def test_paddle_handwriting_fallback_runs_before_template_matching(self) -> None:
        """Prefer the optional Paddle recognizer when it returns a valid number."""
        result = OCREngine(
            FakeBackend("", 0.0),
            paddle_handwriting_recognizer=FakePaddleRecognizer("3.20", 0.88),
            handwriting_recognizer=FakeHandwritingRecognizer("7.50", 0.92),
        ).read_number(self.crop, "W")

        self.assertEqual(result.text, "3.20")
        self.assertEqual(result.parsed_value, 3.2)
        self.assertEqual(result.raw_output["backend"], "paddleocr")

    def test_baseline_result_wins_when_it_is_confident(self) -> None:
        """Keep a strong baseline OCR result instead of replacing it."""
        result = OCREngine(
            FakeBackend("8.25", 0.95),
            handwriting_recognizer=FakeHandwritingRecognizer("7.50", 0.99),
        ).read_number(self.crop, "W")

        self.assertEqual(result.text, "8.25")
        self.assertEqual(result.parsed_value, 8.25)

    def test_mouse_id_preserves_leading_zeroes(self) -> None:
        """Keep printed ID text intact while providing a numeric parsed value."""
        result = OCREngine(
            FakeBackend(" 0012 ", 0.88),
            enable_personal_handwriting=False,
        ).read_printed_mouse_id(self.crop)

        self.assertEqual(result.text, "0012")
        self.assertEqual(result.parsed_value, 12.0)

    def test_mouse_id_normalizes_common_digit_confusions(self) -> None:
        """Map simple printed OCR confusions like O/I to the intended digits."""
        result = OCREngine(
            FakeBackend(" OI3 ", 0.91),
            enable_personal_handwriting=False,
        ).read_printed_mouse_id(self.crop)

        self.assertEqual(result.text, "013")
        self.assertEqual(result.parsed_value, 13.0)

    def test_mouse_id_uses_paddle_when_baseline_backend_is_unavailable(self) -> None:
        """Recover a printed ID from the local Paddle path when Tesseract is absent."""
        result = OCREngine(
            backend=FakeBackend("", 0.0),
            paddle_handwriting_recognizer=FakePaddleRecognizer("27", 0.89),
            enable_personal_handwriting=False,
        ).read_printed_mouse_id(self.crop)

        self.assertEqual(result.text, "27")
        self.assertEqual(result.parsed_value, 27.0)
        self.assertEqual(result.raw_output["backend"], "paddleocr")

    def test_mouse_id_variants_include_colored_cell_printed_mask(self) -> None:
        """Prepare a dedicated dark-digit view for printed IDs on colored fills."""
        colored = np.full((70, 150, 3), (190, 205, 238), dtype=np.uint8)
        cv2.putText(
            colored,
            "27",
            (35, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.3,
            (20, 20, 20),
            3,
            cv2.LINE_AA,
        )

        variants = _prepare_mouse_id_variants(colored)
        variant_names = {variant.name for variant in variants}
        printed_mask = next(
            variant for variant in variants if variant.name == "printed_mask"
        )

        self.assertIn("single_word_otsu", variant_names)
        self.assertIn("printed_mask_raw_line", variant_names)
        self.assertEqual(printed_mask.page_segmentation_mode, 8)
        self.assertLess(int(printed_mask.image.min()), 80)

    def test_default_backend_fails_safely_when_unavailable(self) -> None:
        """Return a missing result if optional Tesseract is unavailable."""
        result = OCREngine(enable_personal_handwriting=False).read_number(self.crop, "W")

        self.assertIsNone(result.parsed_value)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn("backend", result.raw_output)

    def test_cross_out_detects_drawn_x(self) -> None:
        """Flag two long crossing diagonal strokes in a cell."""
        crossed = np.full((100, 200, 3), 255, dtype=np.uint8)
        cv2.line(crossed, (30, 20), (170, 80), (0, 0, 0), 4)
        cv2.line(crossed, (30, 80), (170, 20), (0, 0, 0), 4)
        crossed_path = Path(self.temporary.name) / "crossed.png"
        cv2.imwrite(str(crossed_path), crossed)

        self.assertTrue(
            OCREngine(
                FakeBackend("", 0),
                enable_personal_handwriting=False,
            ).detect_cross_out(crossed_path)
        )


if __name__ == "__main__":
    unittest.main()
