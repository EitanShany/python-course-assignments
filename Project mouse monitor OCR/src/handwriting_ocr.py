"""Personal numeric handwriting recognizer built from reviewer corrections."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import re
from typing import Any

import cv2
import numpy as np

from .learning_store import DEFAULT_LEARNING_FOLDER, load_corrections
from .validation import DEFAULT_RANGES


SUPPORTED_FIELDS = {"W", "L", "Weight"}
SUPPORTED_CHARACTERS = set("0123456789.-")
TEMPLATE_SIZE = 32
MAX_LABEL_VARIANTS = 3
MIN_INK_PIXELS = 8
MIN_INK_RATIO = 0.003
MIN_FULL_VALUE_SIMILARITY = 0.90
MIN_CHARACTER_SIMILARITY = 0.90
MIN_EMPTY_TEMPLATE_SIMILARITY = 0.90


@dataclass(frozen=True)
class CharacterTemplate:
    """One normalized handwritten character learned from a corrected cell."""

    character: str
    image: np.ndarray
    source_crop: str


@dataclass(frozen=True)
class FullValueTemplate:
    """One normalized full-cell handwritten value learned from a correction."""

    label: str
    image: np.ndarray
    source_crop: str
    field_name: str
    glyph_count: int


@dataclass(frozen=True)
class EmptyValueTemplate:
    """One crop explicitly corrected to an empty measurement."""

    image: np.ndarray
    source_crop: str
    field_name: str
    glyph_count: int


class PersonalHandwritingRecognizer:
    """Recognize numeric handwriting by matching against prior corrections."""

    def __init__(self, learning_folder: Path | str = DEFAULT_LEARNING_FOLDER) -> None:
        """Load usable correction crops from the local learning folder."""
        self.learning_folder = Path(learning_folder)
        self.character_templates: list[CharacterTemplate] = []
        self.full_value_templates: list[FullValueTemplate] = []
        self.empty_value_templates: list[EmptyValueTemplate] = []
        self._load_templates()

    @property
    def template_count(self) -> int:
        """Return the number of learned full-value and character templates."""
        return (
            len(self.full_value_templates)
            + len(self.character_templates)
            + len(self.empty_value_templates)
        )

    def recognize_number(
        self,
        crop_image_path: Path | str,
        field_name: str,
    ) -> tuple[str, float, dict[str, Any]]:
        """Return the best personal-handwriting numeric candidate for one crop."""
        if field_name not in SUPPORTED_FIELDS:
            raise ValueError("field_name must be W, L, or Weight.")

        raw_output: dict[str, Any] = {
            "backend": "personal_handwriting",
            "template_count": self.template_count,
        }
        if self.template_count == 0:
            raw_output["error"] = "No corrected handwriting examples are available yet."
            return "", 0.0, raw_output

        crop = _load_crop(crop_image_path)
        if not _has_usable_ink(crop):
            raw_output["error"] = "No usable handwriting ink was found in the crop."
            return "", 0.0, raw_output
        if self._matches_learned_empty(crop, field_name):
            raw_output["method"] = "learned_empty_template"
            return "", 1.0, raw_output
        candidates: list[tuple[str, float, str]] = []

        full_candidate = self._recognize_by_full_value(crop, field_name)
        if full_candidate is not None:
            candidates.append(full_candidate)

        character_candidate = self._recognize_by_characters(crop)
        if character_candidate is not None:
            candidates.append(character_candidate)

        numeric_candidates = [
            (text, confidence, method)
            for text, confidence, method in candidates
            if _is_numeric_text(text)
        ]
        if not numeric_candidates:
            raw_output["error"] = "No numeric personal-handwriting candidate was found."
            return "", 0.0, raw_output

        text, confidence, method = max(numeric_candidates, key=lambda item: item[1])
        raw_output["method"] = method
        raw_output["candidate_count"] = len(numeric_candidates)
        return text, confidence, raw_output

    def _load_templates(self) -> None:
        """Build full-value and character templates from saved corrections."""
        latest_corrections = {}
        for correction in load_corrections(self.learning_folder):
            if not correction.crop_path:
                continue
            latest_corrections[
                (
                    correction.source_image,
                    correction.mouse_id,
                    correction.field_name,
                )
            ] = correction

        for correction in latest_corrections.values():
            if correction.field_name not in SUPPORTED_FIELDS:
                continue
            if correction.corrected_value is not None:
                minimum, maximum = DEFAULT_RANGES[correction.field_name]
                if not minimum <= correction.corrected_value <= maximum:
                    continue
            crop_path = Path(correction.crop_path)
            if not crop_path.is_file():
                continue
            crop = _load_crop(crop_path)
            if not _has_usable_ink(crop):
                continue
            binary = _prepare_binary(crop)
            glyphs = _segment_glyphs(binary)
            if not glyphs:
                continue
            if correction.corrected_value is None:
                self.empty_value_templates.append(
                    EmptyValueTemplate(
                        image=_normalize_glyph(binary),
                        source_crop=str(crop_path.resolve()),
                        field_name=correction.field_name,
                        glyph_count=len(glyphs),
                    )
                )
                continue

            label_variants = _label_variants(correction.corrected_value)
            if not label_variants:
                continue
            full_image = _normalize_glyph(binary)
            self.full_value_templates.append(
                FullValueTemplate(
                    label=label_variants[0],
                    image=full_image,
                    source_crop=str(crop_path.resolve()),
                    field_name=correction.field_name,
                    glyph_count=len(glyphs),
                )
            )

            label = _matching_label_for_glyphs(label_variants, len(glyphs))
            if label is None:
                continue
            for character, glyph in zip(label, glyphs):
                if character not in SUPPORTED_CHARACTERS:
                    continue
                self.character_templates.append(
                    CharacterTemplate(
                        character=character,
                        image=_normalize_glyph(glyph),
                        source_crop=str(crop_path.resolve()),
                    )
                )

    def _matches_learned_empty(self, crop: np.ndarray, field_name: str) -> bool:
        """Return whether the latest correction marked a matching crop as empty."""
        if not self.empty_value_templates:
            return False
        binary = _prepare_binary(crop)
        glyph_count = len(_segment_glyphs(binary))
        target = _normalize_glyph(binary)
        return any(
            template.field_name == field_name
            and template.glyph_count == glyph_count
            and _similarity(target, template.image) >= MIN_EMPTY_TEMPLATE_SIMILARITY
            for template in self.empty_value_templates
        )

    def _recognize_by_full_value(
        self,
        crop: np.ndarray,
        field_name: str,
    ) -> tuple[str, float, str] | None:
        """Match the entire cell against previously corrected full values."""
        if not self.full_value_templates:
            return None
        binary = _prepare_binary(crop)
        glyph_count = len(_segment_glyphs(binary))
        if glyph_count == 0:
            return None
        target = _normalize_glyph(binary)
        best_label = ""
        best_score = 0.0
        for template in self.full_value_templates:
            if template.field_name != field_name or template.glyph_count != glyph_count:
                continue
            score = _similarity(target, template.image)
            if score > best_score:
                best_score = score
                best_label = template.label
        if best_score < MIN_FULL_VALUE_SIMILARITY:
            return None
        return best_label, _clamp_confidence(best_score), "full_value_template"

    def _recognize_by_characters(
        self, crop: np.ndarray
    ) -> tuple[str, float, str] | None:
        """Segment the cell and classify each glyph by nearest personal template."""
        if not self.character_templates:
            return None
        glyphs = _segment_glyphs(_prepare_binary(crop))
        if not glyphs:
            return None

        characters: list[str] = []
        scores: list[float] = []
        for glyph in glyphs:
            target = _normalize_glyph(glyph)
            best_character = ""
            best_score = 0.0
            for template in self.character_templates:
                score = _similarity(target, template.image)
                if score > best_score:
                    best_score = score
                    best_character = template.character
            if not best_character or best_score < MIN_CHARACTER_SIMILARITY:
                return None
            characters.append(best_character)
            scores.append(best_score)

        text = "".join(characters)
        if text.count(".") > 1 or text.count("-") > 1 or ("-" in text[1:]):
            return None
        confidence = sum(scores) / len(scores)
        confidence *= min(1.0, len(self.character_templates) / 10.0)
        return text, _clamp_confidence(confidence), "character_templates"


def _load_crop(path: Path | str) -> np.ndarray:
    """Decode a crop image with path validation."""
    crop_path = Path(path)
    if not crop_path.is_file():
        raise FileNotFoundError(f"Handwriting crop not found: {crop_path.resolve()}")
    encoded = np.frombuffer(crop_path.read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"OpenCV could not decode handwriting crop: {crop_path}")
    return image


def _prepare_binary(crop: np.ndarray) -> np.ndarray:
    """Return a binary image with handwriting ink as white foreground pixels."""
    return _trim_empty_border(_binary_foreground(crop))


def _binary_foreground(crop: np.ndarray) -> np.ndarray:
    """Create a full-size binary foreground image from a crop."""
    if crop.ndim == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    elif crop.ndim == 2:
        gray = crop
    else:
        raise ValueError("Handwriting crop must be grayscale or BGR.")
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )[1]
    return _remove_table_lines(binary)


def _has_usable_ink(crop: np.ndarray) -> bool:
    """Return whether the cell interior contains ink rather than borders or shadows."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    smoothed = cv2.GaussianBlur(gray, (3, 3), 0)
    background = float(np.percentile(smoothed, 90))
    foreground = np.where(smoothed < background - 20.0, 255, 0).astype(np.uint8)
    foreground = _remove_table_lines(foreground)
    height, width = foreground.shape
    margin_x, margin_y = max(1, width // 12), max(1, height // 6)
    interior = foreground[margin_y : height - margin_y, margin_x : width - margin_x]
    if interior.size == 0:
        return False
    ink_pixels = int(np.count_nonzero(interior))
    ink_ratio = ink_pixels / float(interior.size)
    return ink_pixels >= MIN_INK_PIXELS and ink_ratio >= MIN_INK_RATIO


def _remove_table_lines(binary: np.ndarray) -> np.ndarray:
    """Remove long horizontal and vertical grid lines from a binary cell crop."""
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


def _segment_glyphs(binary: np.ndarray) -> list[np.ndarray]:
    """Split foreground ink into left-to-right glyph components."""
    if binary.size == 0:
        return []
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    min_area = max(4, round(binary.size * 0.0004))
    components: list[tuple[int, np.ndarray]] = []
    for component_id in range(1, component_count):
        x, y, width, height, area = stats[component_id]
        if area < min_area or width < 2 or height < 3:
            continue
        glyph = np.where(labels[y : y + height, x : x + width] == component_id, 255, 0)
        components.append((int(x), glyph.astype(np.uint8)))
    return [glyph for _, glyph in sorted(components, key=lambda item: item[0])]


def _normalize_glyph(binary: np.ndarray) -> np.ndarray:
    """Normalize one glyph or full cell to a fixed template canvas."""
    trimmed = _trim_empty_border(binary)
    if trimmed.size == 0 or np.count_nonzero(trimmed) == 0:
        return np.zeros((TEMPLATE_SIZE, TEMPLATE_SIZE), dtype=np.uint8)

    height, width = trimmed.shape[:2]
    scale = min((TEMPLATE_SIZE - 6) / width, (TEMPLATE_SIZE - 6) / height)
    resized_width = max(1, round(width * scale))
    resized_height = max(1, round(height * scale))
    resized = cv2.resize(
        trimmed,
        (resized_width, resized_height),
        interpolation=cv2.INTER_AREA,
    )
    canvas = np.zeros((TEMPLATE_SIZE, TEMPLATE_SIZE), dtype=np.uint8)
    x = (TEMPLATE_SIZE - resized_width) // 2
    y = (TEMPLATE_SIZE - resized_height) // 2
    canvas[y : y + resized_height, x : x + resized_width] = resized
    return canvas


def _trim_empty_border(binary: np.ndarray) -> np.ndarray:
    """Crop away empty rows and columns around foreground ink."""
    if binary.size == 0:
        return binary
    points = cv2.findNonZero(binary)
    if points is None:
        return np.zeros((1, 1), dtype=np.uint8)
    x, y, width, height = cv2.boundingRect(points)
    return binary[y : y + height, x : x + width].copy()


def _similarity(left: np.ndarray, right: np.ndarray) -> float:
    """Return foreground overlap so blank background cannot dominate the score."""
    left_mask = left > 0
    right_mask = right > 0
    foreground_total = int(np.count_nonzero(left_mask)) + int(
        np.count_nonzero(right_mask)
    )
    if foreground_total == 0:
        return 0.0
    intersection = int(np.count_nonzero(left_mask & right_mask))
    return (2.0 * intersection) / foreground_total


def _label_variants(value: float) -> list[str]:
    """Return likely written forms for a numeric correction label."""
    decimal_value = Decimal(str(float(value))).quantize(Decimal("0.01"))
    fixed = format(decimal_value, ".2f")
    stripped = fixed.rstrip("0").rstrip(".")
    variants = [fixed]
    if stripped and stripped != fixed:
        variants.append(stripped)
    integer_text = str(int(decimal_value)) if decimal_value == int(decimal_value) else ""
    if integer_text and integer_text not in variants:
        variants.append(integer_text)
    return [
        variant
        for variant in variants[:MAX_LABEL_VARIANTS]
        if variant and set(variant).issubset(SUPPORTED_CHARACTERS)
    ]


def _matching_label_for_glyphs(labels: list[str], glyph_count: int) -> str | None:
    """Choose the label variant whose character count matches segmented glyphs."""
    for label in labels:
        if len(label) == glyph_count:
            return label
    return None


def _is_numeric_text(text: str) -> bool:
    """Validate a numeric handwritten candidate before handing it to the OCR engine."""
    return bool(re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text))


def _clamp_confidence(confidence: float) -> float:
    """Keep recognizer confidence inside the standard OCR range."""
    return max(0.0, min(1.0, float(confidence)))
