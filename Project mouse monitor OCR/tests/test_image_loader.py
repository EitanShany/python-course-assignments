"""Tests for safe upload persistence and basic OpenCV preprocessing."""

from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

from src.image_loader import (
    MAX_UPLOAD_BYTES,
    correct_perspective,
    deskew,
    estimate_skew_angle,
    load_uploaded_image,
)


class FakeUpload:
    """Small Streamlit UploadedFile-compatible test double."""

    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        """Return uploaded bytes."""
        return self._content


class ImageLoaderTests(unittest.TestCase):
    """Verify safe naming, consistent arrays, and placeholder isolation."""

    def test_saves_and_preprocesses_uploaded_image(self) -> None:
        """Decode a phone-like upload into BGR, grayscale, and binary stages."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = np.zeros((40, 60, 3), dtype=np.uint8)
            source[:, 30:] = 220
            success, encoded = cv2.imencode(".png", source)
            self.assertTrue(success)
            upload = FakeUpload("../unsafe sheet.png", encoded.tobytes())

            result = load_uploaded_image(upload, folder)

            self.assertEqual(result.original_bgr.shape, (40, 60, 3))
            self.assertEqual(result.original_bgr.dtype, np.uint8)
            self.assertEqual(result.grayscale.shape, (40, 60))
            self.assertEqual(result.thresholded.shape, (40, 60))
            self.assertTrue(set(np.unique(result.thresholded)).issubset({0, 255}))
            self.assertEqual(result.metadata.channels, 3)
            self.assertEqual(result.metadata.source_name, "unsafe sheet.png")
            self.assertEqual(result.metadata.saved_path.parent, folder.resolve())
            self.assertNotIn(" ", result.metadata.safe_filename)
            self.assertTrue(result.metadata.saved_path.is_file())
            self.assertIsNot(result.deskewed, result.thresholded)
            self.assertIsNot(result.perspective_corrected, result.deskewed)

    def test_rejects_invalid_image_bytes(self) -> None:
        """Report a clear error when OpenCV cannot decode the upload."""
        with tempfile.TemporaryDirectory() as temporary:
            upload = FakeUpload("broken.png", b"not an image")

            with self.assertRaisesRegex(ValueError, "could not decode"):
                load_uploaded_image(upload, temporary)

    def test_rejects_oversized_upload_before_decode(self) -> None:
        """Bound memory and disk usage for untrusted phone-image uploads."""
        with tempfile.TemporaryDirectory() as temporary:
            upload = FakeUpload("huge.jpg", b"0" * (MAX_UPLOAD_BYTES + 1))

            with self.assertRaisesRegex(ValueError, "25 MB limit"):
                load_uploaded_image(upload, temporary)

    def test_group_name_panel_is_masked_before_local_storage(self) -> None:
        """Remove the upper-left legend area from locally stored review images."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = np.full((200, 300, 3), 255, dtype=np.uint8)
            source[:40, :80] = 0
            source[140:180, 180:240] = 0
            success, encoded = cv2.imencode(".png", source)
            self.assertTrue(success)
            upload = FakeUpload("panel.png", encoded.tobytes())

            result = load_uploaded_image(upload, folder)

            self.assertGreater(float(result.original_bgr[:40, :80, :].mean()), 245.0)
            self.assertLess(
                float(result.original_bgr[140:180, 180:240, :].mean()),
                15.0,
            )

    def test_group_name_redaction_stops_before_lower_table_area(self) -> None:
        """Keep the first data rows intact when the legend occupies only the very top-left."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = np.full((240, 360, 3), 255, dtype=np.uint8)
            source[:32, :70] = 0
            source[90:130, :70] = 25
            success, encoded = cv2.imencode(".png", source)
            self.assertTrue(success)
            upload = FakeUpload("panel_gap.png", encoded.tobytes())

            result = load_uploaded_image(upload, folder)

            self.assertGreater(float(result.original_bgr[:32, :70, :].mean()), 245.0)
            self.assertLess(float(result.original_bgr[90:130, :70, :].mean()), 60.0)

    def test_group_name_redaction_stops_above_table_header_line(self) -> None:
        """Do not erase the first cage rows when a long table header line is visible below."""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = np.full((420, 360, 3), 255, dtype=np.uint8)
            source[40:120, 30:120] = 0
            cv2.line(source, (20, 145), (340, 145), (0, 0, 0), 4)
            source[165:230, 10:60] = 0
            success, encoded = cv2.imencode(".png", source)
            self.assertTrue(success)
            upload = FakeUpload("panel_table.png", encoded.tobytes())

            result = load_uploaded_image(upload, folder)

            self.assertGreater(float(result.original_bgr[40:120, 30:120, :].mean()), 245.0)
            self.assertLess(float(result.original_bgr[165:230, 10:60, :].mean()), 40.0)

    def test_load_uploaded_image_applies_phone_exif_orientation(self) -> None:
        """Honor EXIF rotation so phone photos stay upright for OCR and table detection."""
        with tempfile.TemporaryDirectory() as temporary:
            source = np.full((40, 60, 3), 255, dtype=np.uint8)
            source[:, :15] = 0
            pil_image = Image.fromarray(cv2.cvtColor(source, cv2.COLOR_BGR2RGB))
            exif = Image.Exif()
            exif[274] = 6
            output_path = Path(temporary) / "phone.jpg"
            pil_image.save(output_path, format="JPEG", exif=exif)
            upload = FakeUpload("phone.jpg", output_path.read_bytes())

            result = load_uploaded_image(upload, Path(temporary))

            self.assertEqual(result.original_bgr.shape[:2], (60, 40))
            self.assertLess(float(result.original_bgr[:10, 20:, :].mean()), 40.0)

    def test_correct_perspective_straightens_large_quadrilateral(self) -> None:
        """Warp a phone-like tilted page region into a rectangular image."""
        image = np.full((300, 420, 3), 40, dtype=np.uint8)
        corners = np.array([[70, 35], [350, 60], [330, 260], [55, 235]], dtype=np.int32)
        cv2.fillConvexPoly(image, corners, (245, 245, 245))
        cv2.polylines(image, [corners], isClosed=True, color=(0, 0, 0), thickness=3)

        corrected = correct_perspective(image)

        self.assertEqual(corrected.ndim, 3)
        self.assertGreater(corrected.shape[0], 150)
        self.assertGreater(corrected.shape[1], 200)
        self.assertGreater(float(corrected.mean()), 180.0)

    def test_estimate_skew_angle_detects_rotated_horizontal_line(self) -> None:
        """Measure the dominant small rotation angle from a simple synthetic line."""
        image = np.full((220, 220), 255, dtype=np.uint8)
        cv2.line(image, (30, 140), (190, 108), 0, 4)

        angle = estimate_skew_angle(image)

        self.assertLess(angle, -5.0)
        self.assertGreater(angle, -20.0)

    def test_deskew_rotates_binary_image_toward_horizontal(self) -> None:
        """Reduce the measured skew of a thresholded synthetic page line."""
        image = np.full((220, 220), 255, dtype=np.uint8)
        cv2.line(image, (30, 140), (190, 108), 0, 4)

        before = estimate_skew_angle(image)
        corrected = deskew(image)
        after = estimate_skew_angle(corrected)

        self.assertEqual(corrected.shape, image.shape)
        self.assertLess(abs(after), abs(before))
        self.assertLess(abs(after), 2.5)

    def test_estimate_skew_angle_returns_zero_without_reliable_lines(self) -> None:
        """Avoid inventing a rotation when the page lacks long horizontal structure."""
        image = np.full((180, 180), 255, dtype=np.uint8)
        cv2.circle(image, (90, 90), 10, 0, 2)

        angle = estimate_skew_angle(image)

        self.assertEqual(angle, 0.0)

    def test_deskew_leaves_nearly_straight_page_unchanged(self) -> None:
        """Skip tiny rotations so clean pages are not blurred unnecessarily."""
        image = np.full((220, 220), 255, dtype=np.uint8)
        cv2.line(image, (20, 110), (200, 110), 0, 3)

        corrected = deskew(image)

        self.assertEqual(corrected.shape, image.shape)
        self.assertTrue(np.array_equal(corrected, image))


if __name__ == "__main__":
    unittest.main()
