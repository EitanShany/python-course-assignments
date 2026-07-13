"""Tests for future handwriting dataset preparation."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from src.learning_store import (
    CORRECTIONS_FILENAME,
    PENDING_CORRECTIONS_FILENAME,
    save_correction,
)
from src.review_model import FieldCorrection
from src.train_handwriting_model import prepare_training_data


class TrainingPreparationTests(unittest.TestCase):
    """Verify crop checks, statistics, labels, and deterministic splitting."""

    def setUp(self) -> None:
        """Create isolated correction metadata with four labeled crops."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.learning = self.root / "learning_data"
        self.learning.mkdir()
        self.crops: list[Path] = []
        for index, (field_name, label) in enumerate(
            (("W", 0.0), ("W", 1.25), ("L", 2.5), ("Weight", 20.0)), start=1
        ):
            crop = self.root / f"crop_{index}.png"
            crop.write_bytes(f"crop-{index}".encode())
            self.crops.append(crop)
            save_correction(
                FieldCorrection(
                    source_image="page.jpg",
                    mouse_id=str(index),
                    field_name=field_name,
                    original_prediction=None,
                    corrected_value=label,
                    crop_path=str(crop),
                ),
                self.learning,
            )

    def test_prepares_split_and_prints_statistics(self) -> None:
        """Build deterministic train/validation sets with two-decimal labels."""
        output = StringIO()
        with redirect_stdout(output):
            dataset = prepare_training_data(
                self.learning / CORRECTIONS_FILENAME,
                validation_fraction=0.25,
                random_seed=7,
            )

        self.assertEqual(dataset.statistics.corrected_samples, 4)
        self.assertEqual(
            dataset.statistics.samples_per_field,
            {"W": 2, "L": 1, "Weight": 1},
        )
        self.assertEqual(
            dataset.statistics.unique_corrected_labels,
            ["0.00", "1.25", "2.50", "20.00"],
        )
        self.assertEqual(len(dataset.train_samples), 3)
        self.assertEqual(len(dataset.validation_samples), 1)
        self.assertIn("Corrected samples: 4", output.getvalue())

    def test_missing_crop_stops_preparation(self) -> None:
        """Reject stale correction metadata instead of silently training without it."""
        self.crops[0].unlink()

        with self.assertRaisesRegex(FileNotFoundError, "correction crop"):
            prepare_training_data(self.learning / CORRECTIONS_FILENAME)

    def test_latest_label_replaces_stale_label_for_same_mouse_field(self) -> None:
        """Exclude superseded corrections from future model training data."""
        latest_crop = self.root / "latest_crop.png"
        latest_crop.write_bytes(b"latest-crop")
        save_correction(
            FieldCorrection(
                source_image="page.jpg",
                mouse_id="1",
                field_name="W",
                original_prediction=0.0,
                corrected_value=3.25,
                crop_path=str(latest_crop),
            ),
            self.learning,
        )

        dataset = prepare_training_data(
            self.learning / CORRECTIONS_FILENAME,
            validation_fraction=0,
        )

        self.assertEqual(dataset.statistics.corrected_samples, 4)
        self.assertIn("3.25", dataset.statistics.unique_corrected_labels)
        self.assertNotIn("0.00", dataset.statistics.unique_corrected_labels)

    def test_out_of_range_label_is_excluded_from_training(self) -> None:
        """Do not let malformed workbook or review values poison future training."""
        invalid_crop = self.root / "invalid_crop.png"
        invalid_crop.write_bytes(b"invalid-crop")
        save_correction(
            FieldCorrection(
                source_image="other_page.jpg",
                mouse_id="99",
                field_name="L",
                original_prediction=None,
                corrected_value=842.0,
                crop_path=str(invalid_crop),
            ),
            self.learning,
        )

        dataset = prepare_training_data(
            self.learning / CORRECTIONS_FILENAME,
            validation_fraction=0,
        )

        self.assertEqual(dataset.statistics.corrected_samples, 4)
        self.assertEqual(dataset.statistics.skipped_invalid_labels, 1)
        self.assertNotIn("842.00", dataset.statistics.unique_corrected_labels)

    def test_pending_corrections_file_is_accepted_when_primary_csv_is_missing(self) -> None:
        """Allow future training prep to read fallback-saved correction data."""
        pending = self.learning / PENDING_CORRECTIONS_FILENAME
        (self.learning / CORRECTIONS_FILENAME).replace(pending)

        dataset = prepare_training_data(
            self.learning / CORRECTIONS_FILENAME,
            validation_fraction=0,
        )

        self.assertEqual(dataset.statistics.corrected_samples, 4)
        self.assertEqual(len(dataset.train_samples), 4)


if __name__ == "__main__":
    unittest.main()
