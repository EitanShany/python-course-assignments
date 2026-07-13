"""Tests for the optional PaddleOCR handwriting adapter."""

from pathlib import Path
import tempfile
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from src.paddle_handwriting_ocr import PaddleHandwritingRecognizer


class FakeResult:
    """Expose the documented PaddleOCR JSON result attribute."""

    def __init__(self, payload: object) -> None:
        self.json = payload


class FakeModel:
    """Return one configured result without importing PaddleOCR."""

    def __init__(self, result: FakeResult) -> None:
        self.result = result
        self.calls: list[tuple[str, int]] = []

    def predict(self, *, input: str, batch_size: int) -> list[FakeResult]:
        self.calls.append((input, batch_size))
        return [self.result]


def _write_test_crop(path: Path) -> None:
    """Create a tiny valid image file so OpenCV preprocessing can run in tests."""
    image = np.full((24, 40, 3), 255, dtype=np.uint8)
    cv2.putText(image, "3.2", (2, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    encoded_ok, encoded = cv2.imencode(".png", image)
    assert encoded_ok
    path.write_bytes(encoded.tobytes())


def test_recognizer_returns_text_confidence_and_model_diagnostics() -> None:
    """Adapt a valid PaddleOCR result to the existing recognizer protocol."""
    with tempfile.TemporaryDirectory() as temporary:
        crop = Path(temporary) / "cell.png"
        _write_test_crop(crop)
        model = FakeModel(FakeResult({"res": {"rec_text": "3.20", "rec_score": 0.91}}))
        factory_calls: list[dict[str, object]] = []

        def factory(**kwargs: object) -> FakeModel:
            factory_calls.append(kwargs)
            return model

        recognizer = PaddleHandwritingRecognizer(model_factory=factory)
        text, confidence, raw_output = recognizer.recognize_number(crop, "W")

        assert text == "3.20"
        assert confidence == pytest.approx(0.91)
        assert raw_output["backend"] == "paddleocr"
        assert factory_calls[0]["model_name"] == "en_PP-OCRv5_mobile_rec"
        assert len(model.calls) == 1


def test_recognizer_accepts_mouse_id_field() -> None:
    """Allow the printed mouse-ID path to reuse the same local Paddle model."""
    with tempfile.TemporaryDirectory() as temporary:
        crop = Path(temporary) / "cell.png"
        _write_test_crop(crop)
        model = FakeModel(FakeResult({"res": {"rec_text": "12", "rec_score": 0.87}}))
        recognizer = PaddleHandwritingRecognizer(model_factory=lambda **_: model)

        text, confidence, raw_output = recognizer.recognize_number(crop, "mouse_id")

        assert text == "12"
        assert confidence == pytest.approx(0.87)
        assert raw_output["backend"] == "paddleocr"


def test_recognizer_rejects_malformed_result() -> None:
    """Fail safely instead of trusting an unexpected third-party result shape."""
    with tempfile.TemporaryDirectory() as temporary:
        crop = Path(temporary) / "cell.png"
        _write_test_crop(crop)
        model = FakeModel(FakeResult({"res": "invalid"}))
        recognizer = PaddleHandwritingRecognizer(model_factory=lambda **_: model)

        with pytest.raises(ValueError, match="must be an object"):
            recognizer.recognize_number(crop, "L")


def test_recognizer_requires_local_model_cache_when_factory_is_default() -> None:
    """Fail safely instead of downloading a model when no local cache is present."""
    with tempfile.TemporaryDirectory() as temporary:
        crop = Path(temporary) / "cell.png"
        _write_test_crop(crop)
        recognizer = PaddleHandwritingRecognizer()

        with (
            patch("src.paddle_handwriting_ocr._configure_local_model_cache", return_value=Path(temporary)),
            patch("src.paddle_handwriting_ocr._resolve_local_model_dir", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="fully local"):
                recognizer.recognize_number(crop, "Weight")
