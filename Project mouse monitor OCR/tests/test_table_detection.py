"""Tests for fixed-layout table approximation and cell crop generation."""

from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from src.table_detection import (
    BoundingBox,
    MAX_MOUSE_ROWS,
    detect_grid_boundaries,
    detect_table,
    expected_cell_regions,
)


class TableDetectionTests(unittest.TestCase):
    """Verify cell-by-cell geometry, cage grouping, crops, and debug output."""

    def test_expected_regions_cover_five_fields_per_mouse_row(self) -> None:
        """Return 150 distinct field regions for a full 30-row page."""
        regions = expected_cell_regions(BoundingBox(10, 20, 1000, 900))

        self.assertEqual(len(regions), MAX_MOUSE_ROWS * 5)
        first_row = [region for region in regions if region.page_row == 1]
        self.assertEqual(
            {region.field_name for region in first_row},
            {"mouse_id", "W", "L", "Weight", "Comment"},
        )
        self.assertTrue(all(region.cage_number == 1 for region in first_row))
        final = regions[-1]
        self.assertEqual(final.cage_number, 6)
        self.assertEqual(final.mouse_row_in_cage, 5)

    def test_expected_regions_accept_detected_boundaries(self) -> None:
        """Use detected line positions directly when they are available."""
        table_bbox = BoundingBox(10, 20, 1000, 900)
        row_boundaries = [80, 120, 160]
        field_boundaries = {
            "mouse_id": (90, 140),
            "W": (300, 380),
            "L": (380, 470),
            "Weight": (470, 560),
            "Comment": (560, 700),
        }

        regions = expected_cell_regions(
            table_bbox,
            mouse_rows=2,
            data_bottom_y=160,
            row_boundaries=row_boundaries,
            field_boundaries=field_boundaries,
        )

        first_row = {region.field_name: region for region in regions if region.page_row == 1}
        self.assertEqual(first_row["mouse_id"].bbox.x, 90)
        self.assertEqual(first_row["mouse_id"].bbox.width, 50)
        self.assertEqual(first_row["W"].bbox.y, 80)
        self.assertEqual(first_row["W"].bbox.height, 40)

    def test_detects_synthetic_grid_and_saves_crops_and_debug_image(self) -> None:
        """Detect a page grid and persist one image per expected OCR cell."""
        image = np.full((900, 1200, 3), 255, dtype=np.uint8)
        left, top, right, bottom = 60, 70, 1140, 850
        for x in np.linspace(left, right, 9, dtype=int):
            cv2.line(image, (int(x), top), (int(x), bottom), (0, 0, 0), 2)
        for y in np.linspace(top, bottom, 32, dtype=int):
            cv2.line(image, (left, int(y)), (right, int(y)), (0, 0, 0), 2)

        with tempfile.TemporaryDirectory() as temporary:
            result = detect_table(
                image,
                source_image="phone sheet.jpg",
                crops_folder=temporary,
                debug=True,
            )

            self.assertEqual(result.table_detection_method, "detected_grid")
            self.assertEqual(len(result.cells), 150)
            self.assertTrue(all(cell.crop_path and cell.crop_path.is_file() for cell in result.cells))
            self.assertIsNotNone(result.debug_image_path)
            self.assertTrue(result.debug_image_path.is_file())
            row_one = result.cells_for_row(1)
            self.assertEqual(set(row_one), {"mouse_id", "W", "L", "Weight", "Comment"})
            self.assertEqual(len(list(Path(temporary).glob("*_row*.png"))), 150)
            self.assertLessEqual(abs(row_one["W"].bbox.y - 95), 5)
            self.assertLessEqual(abs(row_one["W"].bbox.y2 - 120), 5)

    def test_blank_page_uses_relative_fallback(self) -> None:
        """Still create usable relative cells when no table lines are detected."""
        image = np.full((500, 800), 255, dtype=np.uint8)
        with tempfile.TemporaryDirectory() as temporary:
            result = detect_table(image, crops_folder=temporary, mouse_rows=2)

            self.assertEqual(result.table_detection_method, "relative_margin_fallback")
            self.assertEqual(len(result.cells), 10)

    def test_detect_grid_boundaries_returns_none_without_enough_lines(self) -> None:
        """Fail softly to the relative layout when the page does not expose a clear grid."""
        image = np.full((400, 600, 3), 255, dtype=np.uint8)

        row_boundaries, field_boundaries = detect_grid_boundaries(
            image,
            BoundingBox(20, 20, 560, 360),
            mouse_rows=4,
            data_bottom_y=360,
        )

        self.assertIsNone(row_boundaries)
        self.assertIsNone(field_boundaries)

    def test_expected_regions_reject_invalid_row_boundaries_length(self) -> None:
        """Guard against callers passing the wrong number of detected row boundaries."""
        with self.assertRaisesRegex(ValueError, "mouse_rows \\+ 1 values"):
            expected_cell_regions(
                BoundingBox(10, 20, 1000, 900),
                mouse_rows=2,
                data_bottom_y=160,
                row_boundaries=[80, 120],
            )

    def test_expected_regions_reject_non_increasing_row_boundaries(self) -> None:
        """Reject degenerate detected row boundaries before crop generation."""
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            expected_cell_regions(
                BoundingBox(10, 20, 1000, 900),
                mouse_rows=2,
                data_bottom_y=160,
                row_boundaries=[80, 120, 120],
            )


if __name__ == "__main__":
    unittest.main()
