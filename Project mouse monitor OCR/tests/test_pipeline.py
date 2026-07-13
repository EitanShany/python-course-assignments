"""Integration tests for the cell-based extraction pipeline."""

from pathlib import Path
import tempfile
import unittest

import numpy as np

from src.image_loader import ImageMetadata, PreprocessedImage
from src.ocr_engine import OCRResult
from src.pipeline import (
    DuplicateExtractedMouseIDError,
    extract_measurements_from_images,
)


class FakeCellEngine:
    """Return deterministic OCR based on crop filename and page name."""

    def __init__(self, duplicate_pages: bool = False) -> None:
        self.duplicate_pages = duplicate_pages

    def read_printed_mouse_id(self, path: Path) -> OCRResult:
        """Read IDs for the first two expected rows only."""
        name = Path(path).name
        row = "1" if "row01" in name else "2" if "row02" in name else None
        if row is None:
            return OCRResult("", None, 0.0, {})
        page_offset = "" if self.duplicate_pages or "page1" in name else "2"
        text = f"{page_offset}10{row}"
        return OCRResult(text, float(int(text)), 0.95, {})

    def read_number(self, path: Path, field_name: str) -> OCRResult:
        """Return complete values for the two populated rows."""
        name = Path(path).name
        if "row01" not in name and "row02" not in name:
            return OCRResult("", None, 0.0, {})
        values = {"W": 1.25, "L": 2.5, "Weight": 22.0}
        value = values[field_name]
        return OCRResult(f"{value:.2f}", value, 0.90, {})

    def detect_comment_or_side_note(self, path: Path) -> bool:
        """Flag the second row as containing a comment."""
        return "row02" in Path(path).name

    def detect_cross_out(self, path: Path) -> bool:
        """Return no cross-outs in this fixture."""
        return False

    def has_visible_content(self, path: Path) -> bool:
        """Mark only the first two mouse rows as populated."""
        name = Path(path).name
        return "row01" in name or "row02" in name


class CommentArtifactEngine(FakeCellEngine):
    """Simulate a grid artifact detected only in an otherwise empty comment cell."""

    def detect_comment_or_side_note(self, path: Path) -> bool:
        """Return a false comment signal for an empty third row."""
        return "row03" in Path(path).name

    def detect_cross_out(self, path: Path) -> bool:
        """Return a false line signal for an empty third row."""
        return "row03" in Path(path).name

    def has_visible_content(self, path: Path) -> bool:
        """Also simulate a false Weight-only signal on the empty third row."""
        name = Path(path).name
        return super().has_visible_content(path) or (
            "row03" in name and name.endswith("_weight.png")
        )


class OutOfRangeValueEngine(FakeCellEngine):
    """Simulate OCR that returns an implausible length despite visible content."""

    def read_number(self, path: Path, field_name: str) -> OCRResult:
        """Return one clearly invalid value for L to test pipeline clamping."""
        if field_name == "L" and "row01" in Path(path).name:
            return OCRResult("1111.00", 1111.0, 0.99, {})
        return super().read_number(path, field_name)


class PartialMouseIDEngine(FakeCellEngine):
    """Recognize only part of the printed sequence while earlier rows stay visible."""

    def read_printed_mouse_id(self, path: Path) -> OCRResult:
        """Return IDs for rows 6-10 and leave earlier visible rows unreadable."""
        name = Path(path).name
        if not any(f"row{row:02d}" in name for row in range(1, 11)):
            return OCRResult("", None, 0.0, {})
        for row in range(6, 11):
            if f"row{row:02d}" in name:
                return OCRResult(str(row), float(row), 0.95, {})
        return OCRResult("", None, 0.0, {})

    def read_number(self, path: Path, field_name: str) -> OCRResult:
        """Keep the first ten rows visible for inference coverage."""
        name = Path(path).name
        if not any(f"row{row:02d}" in name for row in range(1, 11)):
            return OCRResult("", None, 0.0, {})
        values = {"W": 1.25, "L": 2.5, "Weight": 22.0}
        value = values[field_name]
        return OCRResult(f"{value:.2f}", value, 0.90, {})

    def has_visible_content(self, path: Path) -> bool:
        """Mark the first ten rows as populated even when mouse OCR misses some IDs."""
        name = Path(path).name
        return any(f"row{row:02d}" in name for row in range(1, 11))


def make_loaded_image(name: str, folder: Path) -> PreprocessedImage:
    """Create a minimal consistent image-loader result for pipeline testing."""
    image = np.full((500, 800, 3), 255, dtype=np.uint8)
    metadata = ImageMetadata(
        source_name=name,
        safe_filename=name,
        saved_path=folder / name,
        width=800,
        height=500,
        channels=3,
        dtype="uint8",
        file_size_bytes=0,
        sha256="test",
    )
    gray = np.full((500, 800), 255, dtype=np.uint8)
    return PreprocessedImage(metadata, image, gray, gray, gray, gray, gray)


class PipelineTests(unittest.TestCase):
    """Verify integration, validation, duplicate stop, and explicit override."""

    def test_pipeline_creates_validated_measurements_from_cells(self) -> None:
        """Build review models with confidence and comment flags from cell OCR."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result = extract_measurements_from_images(
                [make_loaded_image("page1.png", folder)],
                ocr_engine=FakeCellEngine(),  # type: ignore[arg-type]
                crops_folder=folder,
            )

            self.assertEqual(len(result.measurements), 30)
            first, second = result.measurements[:2]
            self.assertEqual(first.mouse_id, "101")
            self.assertEqual(first.W, 1.25)
            self.assertEqual(first.confidence_Weight, 0.90)
            self.assertFalse(first.approved)
            self.assertTrue(second.comment_detected)
            self.assertTrue(second.requires_manual_review)
            self.assertEqual(result.measurements[2].cage_number, "1")
            self.assertFalse(result.measurements[2].requires_manual_review)
            self.assertEqual(result.measurements[4].cage_number, "1")
            self.assertEqual(result.measurements[5].cage_number, "2")

    def test_duplicates_stop_and_override_retains_results(self) -> None:
        """Stop by default across pages, then allow an explicit continuation."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            images = [
                make_loaded_image("page1.png", folder),
                make_loaded_image("page2.png", folder),
            ]
            with self.assertRaises(DuplicateExtractedMouseIDError) as raised:
                extract_measurements_from_images(
                    images,
                    ocr_engine=FakeCellEngine(duplicate_pages=True),  # type: ignore[arg-type]
                    crops_folder=folder,
                )
            self.assertEqual(set(raised.exception.duplicate_sources), {"101", "102"})
            self.assertEqual(len(raised.exception.result.measurements), 60)

            override = extract_measurements_from_images(
                images,
                ocr_engine=FakeCellEngine(duplicate_pages=True),  # type: ignore[arg-type]
                crops_folder=folder,
                allow_duplicate_mouse_ids=True,
            )
            self.assertEqual(len(override.measurements), 60)

    def test_weight_or_comment_artifact_does_not_mark_empty_slot_for_review(self) -> None:
        """Keep fixed cage slots but do not promote empty slots into warning rows."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result = extract_measurements_from_images(
                [make_loaded_image("page1.png", folder)],
                ocr_engine=CommentArtifactEngine(),  # type: ignore[arg-type]
                crops_folder=folder,
            )

            self.assertEqual(len(result.measurements), 30)
            empty_slot = result.measurements[2]
            self.assertIsNone(empty_slot.mouse_id)
            self.assertFalse(empty_slot.requires_manual_review)
            self.assertEqual(empty_slot.warnings, [])

    def test_implausible_numeric_prediction_is_cleared_before_review(self) -> None:
        """Do not prefill the review table with values outside allowed limits."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result = extract_measurements_from_images(
                [make_loaded_image("page1.png", folder)],
                ocr_engine=OutOfRangeValueEngine(),  # type: ignore[arg-type]
                crops_folder=folder,
            )

            self.assertEqual(result.measurements[0].L, None)
            self.assertEqual(
                result.correction_contexts[0].original_predictions["L"],
                None,
            )

    def test_missing_mouse_ids_stay_blank_when_sequence_has_gaps(self) -> None:
        """Do not invent mouse IDs from row order when some cages may have empty rows."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            result = extract_measurements_from_images(
                [make_loaded_image("page1.png", folder)],
                ocr_engine=PartialMouseIDEngine(),  # type: ignore[arg-type]
                crops_folder=folder,
            )

            first_ten = result.measurements[:10]
            self.assertEqual(len(result.measurements), 30)
            self.assertEqual([row.mouse_id for row in first_ten[:5]], [None, None, None, None, None])
            self.assertIn("Mouse ID is missing or unreadable.", first_ten[0].warnings)
            self.assertEqual(first_ten[5].mouse_id, "6")


if __name__ == "__main__":
    unittest.main()
