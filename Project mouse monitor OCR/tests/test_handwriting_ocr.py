"""Tests for the local personal handwriting recognizer."""

from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from src.handwriting_ocr import PersonalHandwritingRecognizer
from src.learning_store import save_correction
from src.review_model import FieldCorrection


class PersonalHandwritingRecognizerTests(unittest.TestCase):
    """Verify corrected crops become usable local handwriting templates."""

    def test_recognizes_value_from_saved_correction_template(self) -> None:
        """Use a saved correction crop to recognize a matching handwritten value."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            learning_folder = root / "learning_data"
            learning_folder.mkdir()
            crop = root / "value.png"
            self._write_number_image(crop, "7.50")
            save_correction(
                FieldCorrection(
                    source_image="page.jpg",
                    mouse_id="001",
                    field_name="W",
                    original_prediction=None,
                    corrected_value=7.5,
                    crop_path=str(crop),
                ),
                learning_folder,
            )

            recognizer = PersonalHandwritingRecognizer(learning_folder)
            text, confidence, raw_output = recognizer.recognize_number(crop, "W")

            self.assertEqual(text, "7.50")
            self.assertGreaterEqual(confidence, 0.55)
            self.assertEqual(raw_output["backend"], "personal_handwriting")
            self.assertGreater(recognizer.template_count, 0)

    def test_blank_crop_is_not_matched_to_nearest_template(self) -> None:
        """Do not turn an empty measurement cell into a learned value."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            learning_folder = root / "learning_data"
            learning_folder.mkdir()
            template_crop = root / "value.png"
            blank_crop = root / "blank.png"
            self._write_number_image(template_crop, "7.50")
            cv2.imwrite(str(blank_crop), np.full((80, 180, 3), 255, dtype=np.uint8))
            save_correction(
                FieldCorrection(
                    source_image="page.jpg",
                    mouse_id="001",
                    field_name="W",
                    original_prediction=None,
                    corrected_value=7.5,
                    crop_path=str(template_crop),
                ),
                learning_folder,
            )

            recognizer = PersonalHandwritingRecognizer(learning_folder)
            text, confidence, raw_output = recognizer.recognize_number(blank_crop, "W")

            self.assertEqual(text, "")
            self.assertEqual(confidence, 0.0)
            self.assertIn("No usable handwriting ink", raw_output["error"])

    def test_latest_empty_correction_overrides_older_numeric_value(self) -> None:
        """Learn that clearing a previously filled cell means it must stay empty."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            learning_folder = root / "learning_data"
            learning_folder.mkdir()
            old_crop = root / "old_artifact.png"
            latest_crop = root / "latest_artifact.png"
            self._write_number_image(old_crop, "7.50")
            self._write_number_image(latest_crop, "7.50")
            for crop, corrected_value in (
                (old_crop, 7.5),
                (latest_crop, None),
            ):
                save_correction(
                    FieldCorrection(
                        source_image="page.jpg",
                        mouse_id="001",
                        field_name="Weight",
                        original_prediction=7.5,
                        corrected_value=corrected_value,
                        crop_path=str(crop),
                    ),
                    learning_folder,
                )

            recognizer = PersonalHandwritingRecognizer(learning_folder)
            text, confidence, raw_output = recognizer.recognize_number(
                latest_crop,
                "Weight",
            )

            self.assertEqual(text, "")
            self.assertEqual(confidence, 1.0)
            self.assertEqual(raw_output["method"], "learned_empty_template")

    @staticmethod
    def _write_number_image(path: Path, text: str) -> None:
        """Create a simple numeric crop with dark foreground on white background."""
        image = np.full((80, 180, 3), 255, dtype=np.uint8)
        cv2.putText(
            image,
            text,
            (12, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.6,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        success = cv2.imwrite(str(path), image)
        if not success:
            raise OSError(f"Could not write test image: {path}")


if __name__ == "__main__":
    unittest.main()
