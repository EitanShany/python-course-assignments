"""Replaceable baseline OCR interface for individual table-cell crops."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re
import tempfile
from typing import Any, Protocol

import cv2
import numpy as np


NUMERIC_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
MOUSE_ID_PATTERN = re.compile(r"^\d+$")
MIN_VISIBLE_INK_PIXELS = 8
MIN_VISIBLE_INK_RATIO = 0.003


@dataclass(frozen=True)
class OCRResult:
    """Normalized OCR output plus its original engine diagnostics."""

    text: str
    parsed_value: float | None
    confidence: float
    raw_output: Any


@dataclass(frozen=True)
class OCRImageVariant:
    """One prepared OCR image plus its preprocessing label."""

    name: str
    image: np.ndarray
    page_segmentation_mode: int = 7


class OCRBackend(Protocol):
    """Minimal backend contract for replacing Tesseract with a handwriting model."""

    def recognize(
        self,
        image: np.ndarray,
        *,
        character_whitelist: str | None,
        page_segmentation_mode: int,
    ) -> tuple[str, float, Any]:
        """Return text, normalized confidence from 0 to 1, and raw diagnostics."""


class HandwritingRecognizer(Protocol):
    """Optional local recognizer trained from the reviewer's corrections."""

    def recognize_number(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> tuple[str, float, Any]:
        """Return text, confidence, and diagnostics for one handwritten number."""


class TesseractBackend:
    """Simple printed-text baseline implemented with pytesseract."""

    def recognize(
        self,
        image: np.ndarray,
        *,
        character_whitelist: str | None,
        page_segmentation_mode: int,
    ) -> tuple[str, float, Any]:
        """Run Tesseract on one cell and average confidence of non-empty tokens."""
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract is not installed; install requirements.txt or provide another OCR backend."
            ) from exc

        configuration = f"--oem 3 --psm {page_segmentation_mode}"
        if character_whitelist:
            configuration += f" -c tessedit_char_whitelist={character_whitelist}"
        data = pytesseract.image_to_data(
            image,
            config=configuration,
            output_type=Output.DICT,
        )
        tokens: list[str] = []
        confidences: list[float] = []
        for token, raw_confidence in zip(data.get("text", []), data.get("conf", [])):
            token = str(token).strip()
            try:
                confidence = float(raw_confidence)
            except (TypeError, ValueError):
                confidence = -1.0
            if token:
                tokens.append(token)
                if confidence >= 0:
                    confidences.append(confidence / 100.0)
        text = "".join(tokens) if character_whitelist else " ".join(tokens)
        average_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.0
        )
        return text, average_confidence, data


class OCREngine:
    """Cell-based OCR facade with replaceable recognition backend."""

    def __init__(
        self,
        backend: OCRBackend | None = None,
        *,
        paddle_handwriting_recognizer: HandwritingRecognizer | None = None,
        handwriting_recognizer: HandwritingRecognizer | None = None,
        enable_personal_handwriting: bool = True,
        minimum_confidence: float = 0.55,
    ) -> None:
        """Initialize a baseline backend and its acceptance threshold."""
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between 0 and 1.")
        self.backend = backend or TesseractBackend()
        self.paddle_handwriting_recognizer = paddle_handwriting_recognizer
        self.handwriting_recognizer = handwriting_recognizer
        self.enable_personal_handwriting = enable_personal_handwriting
        self.minimum_confidence = minimum_confidence
        self._backend_error: dict[str, str] | None = None
        self._paddle_error: dict[str, str] | None = None

    def read_number(self, crop_image_path: Path | str, field_name: str) -> OCRResult:
        """Read one W/L/Weight cell and accept only a confident numeric value."""
        if field_name not in {"W", "L", "Weight"}:
            raise ValueError("field_name must be W, L, or Weight.")
        crop = _load_crop(crop_image_path)
        if not _has_meaningful_foreground(crop):
            return OCRResult("", None, 0.0, {"empty_cell": True})
        best = self._best_numeric_backend_result(crop, field_name)
        if best.parsed_value is not None:
            return best

        paddle = self._recognize_paddle_handwriting(crop_image_path, field_name)
        if paddle is not None:
            best = _prefer_numeric_candidate(best, paddle)
            if best.parsed_value is not None:
                return best

        personal = self._recognize_personal_handwriting(crop_image_path, field_name)
        if personal is not None:
            best = _prefer_numeric_candidate(best, personal)
        return best

    def _recognize_paddle_handwriting(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> OCRResult | None:
        """Try the optional PaddleOCR recognizer before template-only fallback."""
        if self._paddle_error is not None:
            return OCRResult("", None, 0.0, dict(self._paddle_error))
        try:
            if self.paddle_handwriting_recognizer is None:
                from .paddle_handwriting_ocr import PaddleHandwritingRecognizer

                self.paddle_handwriting_recognizer = PaddleHandwritingRecognizer()
            text, confidence, raw_output = self.paddle_handwriting_recognizer.recognize_number(
                crop_image_path,
                field_name,
            )
            confidence = max(0.0, min(1.0, float(confidence)))
            return self._numeric_result_from_text(
                text,
                confidence,
                raw_output,
                field_name,
            )
        except Exception as exc:
            self._paddle_error = {
                "backend": "paddleocr",
                "error": str(exc),
            }
            return OCRResult("", None, 0.0, dict(self._paddle_error))

    def read_printed_mouse_id(self, crop_image_path: Path | str) -> OCRResult:
        """Read a printed numeric mouse ID while preserving leading zeroes in text."""
        crop = _load_crop(crop_image_path)
        if not _has_meaningful_foreground(crop):
            return OCRResult("", None, 0.0, {"empty_cell": True})
        best = self._best_mouse_id_backend_result(crop)
        if best.parsed_value is not None:
            return best
        paddle = self._recognize_paddle_mouse_id(crop)
        if paddle is not None:
            return _prefer_mouse_id_candidate(best, paddle)
        return best

    def detect_comment_or_side_note(self, crop_image_path: Path | str) -> bool:
        """Flag a comment cell when OCR finds text or the interior contains visible ink."""
        crop = _load_crop(crop_image_path)
        prepared = _prepare_ocr_image(crop)
        text, confidence, _ = self._recognize(
            prepared, character_whitelist=None, page_segmentation_mode=6
        )
        return bool(text.strip() and confidence >= 0.20) or _interior_ink_ratio(crop) >= 0.015

    def detect_cross_out(self, crop_image_path: Path | str) -> bool:
        """Use a conservative line heuristic to flag an X or long strike-through."""
        crop = _load_crop(crop_image_path)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        binary = _remove_table_lines(binary)
        height, width = binary.shape
        margin_x, margin_y = max(1, width // 20), max(1, height // 10)
        interior = binary[margin_y : height - margin_y, margin_x : width - margin_x]
        if interior.size == 0:
            return False
        lines = cv2.HoughLinesP(
            interior,
            1,
            np.pi / 180,
            threshold=max(10, min(interior.shape) // 4),
            minLineLength=max(8, int(interior.shape[1] * 0.35)),
            maxLineGap=max(3, interior.shape[1] // 12),
        )
        if lines is None:
            return False
        diagonal_slopes: list[float] = []
        long_horizontal = False
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            dx, dy = x2 - x1, y2 - y1
            if dx == 0:
                continue
            slope = dy / dx
            if abs(slope) >= 0.25:
                diagonal_slopes.append(slope)
            elif abs(dy) <= max(2, interior.shape[0] * 0.12):
                long_horizontal = True
        has_crossing_diagonals = any(slope > 0 for slope in diagonal_slopes) and any(
            slope < 0 for slope in diagonal_slopes
        )
        return has_crossing_diagonals or long_horizontal

    def has_visible_content(self, crop_image_path: Path | str) -> bool:
        """Return whether a crop contains interior ink, independent of OCR confidence."""
        return _has_meaningful_foreground(_load_crop(crop_image_path))

    def _recognize(
        self,
        image: np.ndarray,
        *,
        character_whitelist: str | None,
        page_segmentation_mode: int,
    ) -> tuple[str, float, Any]:
        """Call the backend and turn an unavailable baseline into a safe missing result."""
        if self._backend_error is not None:
            return "", 0.0, dict(self._backend_error)
        try:
            text, confidence, raw_output = self.backend.recognize(
                image,
                character_whitelist=character_whitelist,
                page_segmentation_mode=page_segmentation_mode,
            )
            confidence = max(0.0, min(1.0, float(confidence)))
            return str(text or ""), confidence, raw_output
        except Exception as exc:  # Backend packages/models are optional and replaceable.
            self._backend_error = {
                "error": str(exc),
                "backend": type(self.backend).__name__,
            }
            return "", 0.0, dict(self._backend_error)

    def _recognize_personal_handwriting(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> OCRResult | None:
        """Try the local personal handwriting recognizer as a numeric fallback."""
        if not self.enable_personal_handwriting:
            return None
        try:
            if self.handwriting_recognizer is None:
                from .handwriting_ocr import PersonalHandwritingRecognizer

                self.handwriting_recognizer = PersonalHandwritingRecognizer()
            text, confidence, raw_output = self.handwriting_recognizer.recognize_number(
                crop_image_path,
                field_name,
            )
            confidence = max(0.0, min(1.0, float(confidence)))
            return self._numeric_result_from_text(
                text,
                confidence,
                raw_output,
                field_name,
            )
        except Exception as exc:
            return OCRResult(
                "",
                None,
                0.0,
                {
                    "backend": "personal_handwriting",
                    "error": str(exc),
                },
            )

    def _best_numeric_backend_result(
        self,
        crop: np.ndarray,
        field_name: str,
    ) -> OCRResult:
        """Try a few safe cell-preprocessing variants and keep the best numeric result."""
        attempts: list[OCRResult] = []
        for variant in _prepare_number_variants(crop):
            raw_text, confidence, raw_output = self._recognize(
                variant.image,
                character_whitelist="0123456789.,-",
                page_segmentation_mode=variant.page_segmentation_mode,
            )
            attempts.append(
                self._numeric_result_from_text(
                    raw_text,
                    confidence,
                    _with_variant_name(raw_output, variant.name),
                    field_name,
                )
            )
        if not attempts:
            return OCRResult("", None, 0.0, {"error": "No OCR image variants available."})
        return max(attempts, key=_result_priority)

    def _best_mouse_id_backend_result(self, crop: np.ndarray) -> OCRResult:
        """Try several printed-ID views so colored cells are less likely to hide digits."""
        attempts: list[OCRResult] = []
        for variant in _prepare_mouse_id_variants(crop):
            raw_text, confidence, raw_output = self._recognize(
                variant.image,
                character_whitelist="0123456789",
                page_segmentation_mode=variant.page_segmentation_mode,
            )
            attempts.append(
                self._mouse_id_result_from_text(
                    raw_text,
                    confidence,
                    _with_variant_name(raw_output, variant.name),
                )
            )
        if not attempts:
            return OCRResult("", None, 0.0, {"error": "No OCR image variants available."})
        return max(attempts, key=_mouse_id_result_priority)

    def _recognize_paddle_mouse_id(self, crop: np.ndarray) -> OCRResult | None:
        """Use the local Paddle recognizer on printed-ID variants when available."""
        if self._paddle_error is not None:
            return OCRResult("", None, 0.0, dict(self._paddle_error))
        try:
            if self.paddle_handwriting_recognizer is None:
                from .paddle_handwriting_ocr import PaddleHandwritingRecognizer

                self.paddle_handwriting_recognizer = PaddleHandwritingRecognizer()
            attempts: list[OCRResult] = []
            with tempfile.TemporaryDirectory(prefix="mouse_id_ocr_") as temporary:
                temp_dir = Path(temporary)
                for index, variant in enumerate(_prepare_mouse_id_variants(crop), start=1):
                    temp_path = temp_dir / f"{index:02d}_{variant.name}.png"
                    _save_temp_image(temp_path, variant.image)
                    text, confidence, raw_output = self.paddle_handwriting_recognizer.recognize_number(
                        temp_path,
                        "mouse_id",
                    )
                    attempts.append(
                        self._mouse_id_result_from_text(
                            text,
                            confidence,
                            _with_variant_name(raw_output, f"paddle_{variant.name}"),
                        )
                    )
            if not attempts:
                return None
            return max(attempts, key=_mouse_id_result_priority)
        except Exception as exc:
            self._paddle_error = {
                "backend": "paddleocr",
                "error": str(exc),
            }
            return OCRResult("", None, 0.0, dict(self._paddle_error))

    def _numeric_result_from_text(
        self,
        raw_text: str,
        confidence: float,
        raw_output: Any,
        field_name: str,
    ) -> OCRResult:
        """Normalize, validate, and optionally accept a numeric OCR candidate."""
        cleaned = _clean_numeric_text(raw_text)
        if not cleaned:
            return OCRResult("", None, min(confidence, 0.10), raw_output)
        candidate = _best_numeric_candidate(cleaned, field_name)
        if candidate is None:
            return OCRResult(cleaned, None, min(confidence, 0.25), raw_output)
        text, decimal_value, inferred_decimal = candidate
        formatted = format(decimal_value, ".2f")
        raw_output = _with_inference_flag(raw_output, inferred_decimal, cleaned, text)
        if not _value_in_expected_range(float(decimal_value), field_name):
            return OCRResult(formatted, None, min(confidence, 0.25), raw_output)
        if confidence < self.minimum_confidence:
            return OCRResult(formatted, None, confidence, raw_output)
        return OCRResult(formatted, float(decimal_value), confidence, raw_output)

    def _mouse_id_result_from_text(
        self,
        raw_text: str,
        confidence: float,
        raw_output: Any,
    ) -> OCRResult:
        """Normalize printed-ID OCR text while preserving leading zeroes."""
        cleaned = _clean_mouse_id_text(raw_text)
        if not cleaned:
            return OCRResult("", None, min(confidence, 0.10), raw_output)
        if not MOUSE_ID_PATTERN.fullmatch(cleaned):
            return OCRResult(cleaned, None, min(confidence, 0.25), raw_output)
        if confidence < self.minimum_confidence:
            return OCRResult(cleaned, None, confidence, raw_output)
        return OCRResult(cleaned, float(int(cleaned)), confidence, raw_output)


def _clean_numeric_text(text: str) -> str:
    """Normalize decimal comma and remove whitespace without guessing other symbols."""
    return re.sub(r"\s+", "", str(text or "").strip()).replace(",", ".")


def _clean_mouse_id_text(text: str) -> str:
    """Normalize common printed-digit OCR confusions conservatively."""
    cleaned = re.sub(r"\s+", "", str(text or "").strip())
    translation = str.maketrans(
        {
            "O": "0",
            "o": "0",
            "I": "1",
            "l": "1",
            "|": "1",
        }
    )
    return cleaned.translate(translation).strip(".,;:_-")


def _best_numeric_candidate(
    cleaned: str,
    field_name: str,
) -> tuple[str, Decimal, bool] | None:
    """Choose one safe numeric interpretation, including cautious decimal recovery."""
    in_range_candidates: list[tuple[str, Decimal, bool]] = []
    fallback_candidates: list[tuple[str, Decimal, bool]] = []
    for candidate_text, inferred_decimal in _numeric_text_candidates(cleaned, field_name):
        if not NUMERIC_PATTERN.fullmatch(candidate_text):
            continue
        try:
            decimal_value = Decimal(candidate_text).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        except InvalidOperation:
            continue
        packed = (candidate_text, decimal_value, inferred_decimal)
        if _value_in_expected_range(float(decimal_value), field_name):
            in_range_candidates.append(packed)
        else:
            fallback_candidates.append(packed)
    if in_range_candidates:
        return in_range_candidates[0]
    if fallback_candidates:
        return fallback_candidates[0]
    return None


def _numeric_text_candidates(
    cleaned: str,
    field_name: str,
) -> list[tuple[str, bool]]:
    """Return direct and cautiously inferred numeric spellings for one OCR token."""
    candidates: list[tuple[str, bool]] = [(cleaned, False)]
    unsigned = cleaned[1:] if cleaned.startswith("-") else cleaned
    sign = "-" if cleaned.startswith("-") else ""
    if "." in unsigned or not unsigned.isdigit():
        return candidates
    inferred: list[str] = []
    if field_name in {"W", "L"}:
        if len(unsigned) == 3:
            inferred.extend(
                [
                    f"{sign}{unsigned[0]}.{unsigned[1:]}",
                    f"{sign}{unsigned[:2]}.{unsigned[2]}",
                ]
            )
        elif len(unsigned) == 4:
            inferred.append(f"{sign}{unsigned[:2]}.{unsigned[2:]}")
    elif field_name == "Weight":
        if len(unsigned) == 3:
            inferred.extend(
                [
                    f"{sign}{unsigned[:2]}.{unsigned[2]}",
                    f"{sign}{unsigned[0]}.{unsigned[1:]}",
                ]
            )
        elif len(unsigned) == 4:
            inferred.append(f"{sign}{unsigned[:2]}.{unsigned[2:]}")
    for candidate in inferred:
        if candidate not in {text for text, _ in candidates}:
            candidates.append((candidate, True))
    return candidates


def _value_in_expected_range(value: float, field_name: str) -> bool:
    """Keep numeric acceptance inside the expected review range per field."""
    maximum = 40.0 if field_name == "Weight" else 20.0
    return 0.0 <= value <= maximum


def _load_crop(path: Path | str) -> np.ndarray:
    """Decode a crop with OpenCV into a consistent BGR image."""
    crop_path = Path(path)
    if not crop_path.is_file():
        raise FileNotFoundError(f"OCR crop not found: {crop_path.resolve()}")
    encoded = np.frombuffer(crop_path.read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"OpenCV could not decode OCR crop: {crop_path}")
    return image


def _prepare_ocr_image(crop: np.ndarray) -> np.ndarray:
    """Upscale and binarize one cell for the simple baseline recognizer."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    return cv2.threshold(
        enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]


def _prepare_mouse_id_variants(crop: np.ndarray) -> list[OCRImageVariant]:
    """Build OCR views that reduce colored fills and enlarge printed digits."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    normalized = _normalize_cell_lighting(gray)
    enlarged = cv2.resize(
        normalized,
        None,
        fx=3.0,
        fy=3.0,
        interpolation=cv2.INTER_CUBIC,
    )
    variants = [
        OCRImageVariant("gray", enlarged),
        OCRImageVariant("otsu", _threshold_black_on_white(enlarged)),
        OCRImageVariant("single_word_otsu", _threshold_black_on_white(enlarged), 8),
    ]
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
    clahe = cv2.resize(clahe, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    variants.append(OCRImageVariant("clahe_otsu", _threshold_black_on_white(clahe), 8))
    printed_mask = _printed_digit_mask_variant(crop)
    if printed_mask is not None:
        variants.extend(
            [
                OCRImageVariant("printed_mask", printed_mask, 8),
                OCRImageVariant("printed_mask_raw_line", printed_mask, 13),
            ]
        )
    adaptive = cv2.adaptiveThreshold(
        enlarged,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        9,
    )
    variants.append(OCRImageVariant("adaptive", adaptive))
    tight = _tight_foreground_variant(enlarged)
    if tight is not None:
        variants.append(OCRImageVariant("tight", tight, 8))
    return variants


def _prepare_number_variants(crop: np.ndarray) -> list[OCRImageVariant]:
    """Build a few safe OCR views so weak handwriting is not judged from one threshold."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    normalized = _normalize_cell_lighting(gray)
    enlarged = cv2.resize(
        normalized,
        None,
        fx=2.5,
        fy=2.5,
        interpolation=cv2.INTER_CUBIC,
    )
    variants = [
        OCRImageVariant("otsu", _threshold_black_on_white(enlarged)),
        OCRImageVariant(
            "adaptive",
            cv2.adaptiveThreshold(
                enlarged,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11,
            ),
        ),
    ]
    tight = _tight_foreground_variant(enlarged)
    if tight is not None:
        variants.append(OCRImageVariant("tight", tight))
    return variants


def _normalize_cell_lighting(grayscale: np.ndarray) -> np.ndarray:
    """Reduce uneven shadows before thresholding one measurement cell."""
    background = cv2.GaussianBlur(grayscale, (0, 0), sigmaX=9, sigmaY=9)
    normalized = cv2.divide(grayscale, background, scale=255)
    return cv2.normalize(normalized, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def _threshold_black_on_white(grayscale: np.ndarray) -> np.ndarray:
    """Threshold to black text on white paper while removing long table lines."""
    binary = cv2.threshold(
        grayscale,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )[1]
    binary = _remove_table_lines(binary)
    return 255 - binary


def _printed_digit_mask_variant(crop: np.ndarray) -> np.ndarray | None:
    """Isolate dark printed digits from colored mouse-ID cells."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    dark = cv2.inRange(value, 0, 170)
    dark[(saturation > 80) & (value > 90)] = 0
    dark = _remove_table_lines(dark)
    dark = cv2.morphologyEx(
        dark,
        cv2.MORPH_OPEN,
        np.ones((2, 2), dtype=np.uint8),
        iterations=1,
    )
    dark = cv2.morphologyEx(
        dark,
        cv2.MORPH_CLOSE,
        np.ones((2, 2), dtype=np.uint8),
        iterations=1,
    )
    points = cv2.findNonZero(dark)
    if points is None:
        return None
    x, y, width, height = cv2.boundingRect(points)
    if width < 3 or height < 6:
        return None
    pad_x = max(3, width // 5)
    pad_y = max(3, height // 4)
    y1 = max(0, y - pad_y)
    y2 = min(gray.shape[0], y + height + pad_y)
    x1 = max(0, x - pad_x)
    x2 = min(gray.shape[1], x + width + pad_x)
    tight = 255 - dark[y1:y2, x1:x2]
    return cv2.resize(tight, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_NEAREST)


def _tight_foreground_variant(grayscale: np.ndarray) -> np.ndarray | None:
    """Crop tightly around detected ink so digits and decimal dots fill more of the OCR view."""
    binary = cv2.threshold(
        grayscale,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )[1]
    binary = _remove_table_lines(binary)
    binary = cv2.dilate(binary, np.ones((2, 2), dtype=np.uint8), iterations=1)
    points = cv2.findNonZero(binary)
    if points is None:
        return None
    x, y, width, height = cv2.boundingRect(points)
    pad_x = max(4, width // 8)
    pad_y = max(4, height // 6)
    y1 = max(0, y - pad_y)
    y2 = min(binary.shape[0], y + height + pad_y)
    x1 = max(0, x - pad_x)
    x2 = min(binary.shape[1], x + width + pad_x)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return 255 - binary[y1:y2, x1:x2]


def _interior_ink_ratio(crop: np.ndarray) -> float:
    """Estimate meaningful dark ink while ignoring borders and lighting gradients."""
    interior = _interior_foreground(crop)
    if interior.size == 0:
        return 0.0
    ink_pixels = int(np.count_nonzero(interior))
    if ink_pixels < MIN_VISIBLE_INK_PIXELS:
        return 0.0
    return ink_pixels / float(interior.size)


def _has_meaningful_foreground(crop: np.ndarray) -> bool:
    """Keep faint, compact handwriting visible without promoting random dust."""
    interior = _interior_foreground(crop)
    if interior.size == 0:
        return False
    ink_pixels = int(np.count_nonzero(interior))
    if ink_pixels < MIN_VISIBLE_INK_PIXELS:
        return False
    return _has_plausible_connected_component(interior)


def _interior_foreground(crop: np.ndarray) -> np.ndarray:
    """Return the cleaned interior foreground mask used by blank-cell heuristics."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    smoothed = cv2.GaussianBlur(gray, (3, 3), 0)
    background = float(np.percentile(smoothed, 90))
    foreground = np.where(smoothed < background - 20.0, 255, 0).astype(np.uint8)
    foreground = _remove_table_lines(foreground)
    height, width = foreground.shape
    margin_x, margin_y = max(1, width // 12), max(1, height // 6)
    return foreground[margin_y : height - margin_y, margin_x : width - margin_x]


def _has_plausible_connected_component(interior: np.ndarray) -> bool:
    """Detect faint digit-like strokes that occupy little total area."""
    component_count, _, stats, _ = cv2.connectedComponentsWithStats(interior, 8)
    minimum_height = max(6, round(interior.shape[0] * 0.12))
    minimum_width = max(2, round(interior.shape[1] * 0.01))
    minimum_area = max(10, round(interior.size * 0.0012))
    for component_index in range(1, component_count):
        width = int(stats[component_index, cv2.CC_STAT_WIDTH])
        height = int(stats[component_index, cv2.CC_STAT_HEIGHT])
        area = int(stats[component_index, cv2.CC_STAT_AREA])
        if area < minimum_area:
            continue
        if height >= minimum_height and width >= minimum_width:
            return True
    return False


def _remove_table_lines(binary: np.ndarray) -> np.ndarray:
    """Remove long grid lines before deciding whether a cell has content."""
    cleaned = binary.copy()
    height, width = cleaned.shape
    lines = cv2.HoughLinesP(
        cleaned,
        1,
        np.pi / 180,
        threshold=max(8, min(height, width) // 3),
        minLineLength=max(8, round(min(height, width) * 0.5)),
        maxLineGap=max(2, round(max(height, width) * 0.08)),
    )
    if lines is not None:
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dx >= width * 0.55 and dy <= height * 0.25:
                cv2.line(
                    cleaned,
                    (x1, y1),
                    (x2, y2),
                    0,
                    thickness=max(3, height // 7),
                )
            elif dy >= height * 0.55 and dx <= width * 0.15:
                cv2.line(
                    cleaned,
                    (x1, y1),
                    (x2, y2),
                    0,
                    thickness=max(3, width // 30),
                )
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(3, round(width * 0.65)), 1),
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (1, max(3, round(height * 0.75))),
    )
    horizontal = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, vertical_kernel)
    cleaned[horizontal > 0] = 0
    cleaned[vertical > 0] = 0
    return cleaned


def _with_variant_name(raw_output: Any, variant_name: str) -> Any:
    """Attach the preprocessing variant to dict diagnostics when possible."""
    if isinstance(raw_output, dict):
        enriched = dict(raw_output)
        enriched["variant"] = variant_name
        return enriched
    return raw_output


def _with_inference_flag(
    raw_output: Any,
    inferred_decimal: bool,
    cleaned_text: str,
    chosen_text: str,
) -> Any:
    """Keep a trace when OCR text needed decimal recovery before validation."""
    if isinstance(raw_output, dict):
        enriched = dict(raw_output)
        enriched["cleaned_text"] = cleaned_text
        enriched["chosen_text"] = chosen_text
        if inferred_decimal:
            enriched["inferred_decimal"] = True
        return enriched
    return raw_output


def _save_temp_image(path: Path, image: np.ndarray) -> None:
    """Persist a temporary OCR variant without relying on imwrite Unicode behavior."""
    success, encoded = cv2.imencode(path.suffix or ".png", image)
    if not success:
        raise OSError(f"OpenCV could not encode OCR variant: {path}")
    path.write_bytes(encoded.tobytes())


def _prefer_numeric_candidate(current: OCRResult, candidate: OCRResult) -> OCRResult:
    """Keep the stronger numeric fallback while preserving useful candidate text."""
    if candidate.parsed_value is not None:
        if current.parsed_value is None or candidate.confidence >= current.confidence:
            return candidate
    if current.parsed_value is None and not current.text and candidate.text:
        return candidate
    return current


def _prefer_mouse_id_candidate(current: OCRResult, candidate: OCRResult) -> OCRResult:
    """Keep the stronger printed-ID result while preserving useful candidate text."""
    if candidate.parsed_value is not None:
        if current.parsed_value is None or candidate.confidence >= current.confidence:
            return candidate
    if current.parsed_value is None and not current.text and candidate.text:
        return candidate
    return current


def _result_priority(result: OCRResult) -> tuple[int, int, float, int]:
    """Prefer valid parsed values, then explicit decimals, then stronger confidence."""
    raw_output = result.raw_output if isinstance(result.raw_output, dict) else {}
    inferred_decimal = bool(raw_output.get("inferred_decimal"))
    return (
        1 if result.parsed_value is not None else 0,
        0 if inferred_decimal else 1,
        float(result.confidence),
        len(result.text),
    )


def _mouse_id_result_priority(result: OCRResult) -> tuple[int, float, int]:
    """Prefer valid parsed IDs, then stronger confidence, then fuller digit strings."""
    return (
        1 if result.parsed_value is not None else 0,
        float(result.confidence),
        len(result.text),
    )
