"""Tests for persistent correction metadata and portable learning exports."""

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from src import learning_store
from src.learning_store import (
    CORRECTIONS_FILENAME,
    PENDING_CORRECTIONS_FILENAME,
    consolidate_learning_files,
    current_run_corrections,
    export_learning_data,
    load_corrections,
    reset_learning_data,
    reset_learning_for_current_run_only,
    save_correction,
)
from src.review_model import FieldCorrection


class LearningStoreTests(unittest.TestCase):
    """Verify changed-value storage, zero labels, ZIP crops, and reset scopes."""

    def setUp(self) -> None:
        """Create isolated learning and crop folders."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.learning = self.root / "learning_data"
        self.learning.mkdir()
        self.crop = self.root / "cell.png"
        self.crop.write_bytes(b"crop image bytes")
        reset_learning_for_current_run_only()

    def _correction(
        self,
        original: float | None = None,
        corrected: float | None = 0.0,
    ) -> FieldCorrection:
        """Build one crop-backed correction fixture."""
        return FieldCorrection(
            source_image="page.jpg",
            mouse_id="001",
            field_name="W",
            original_prediction=original,
            corrected_value=corrected,
            crop_path=str(self.crop),
        )

    def test_saves_and_loads_changed_zero_value(self) -> None:
        """Persist None-to-zero as a real labeled correction with two decimals."""
        self.assertTrue(save_correction(self._correction(), self.learning))

        loaded = load_corrections(self.learning)
        self.assertEqual(len(loaded), 1)
        self.assertIsNone(loaded[0].original_prediction)
        self.assertEqual(loaded[0].corrected_value, 0.0)
        with (self.learning / CORRECTIONS_FILENAME).open(
            newline="", encoding="utf-8"
        ) as csv_file:
            row = next(csv.DictReader(csv_file))
        self.assertEqual(row["original_prediction"], "")
        self.assertEqual(row["corrected_value"], "0.00")
        self.assertEqual(Path(row["crop_path"]), self.crop.resolve())

    def test_unchanged_value_is_not_saved(self) -> None:
        """Do not pollute training data when prediction and review are equal."""
        saved = save_correction(self._correction(2.5, 2.5), self.learning)

        self.assertFalse(saved)
        self.assertFalse((self.learning / CORRECTIONS_FILENAME).exists())

    def test_rejects_blank_mouse_id_and_missing_crop_path(self) -> None:
        """Stop malformed correction records before they can enter learning storage."""
        blank_mouse = self._correction()
        blank_mouse.mouse_id = "   "
        missing_crop = self._correction()
        missing_crop.crop_path = None

        with self.assertRaisesRegex(ValueError, "mouse ID is required"):
            save_correction(blank_mouse, self.learning)
        with self.assertRaisesRegex(ValueError, "crop image path is required"):
            save_correction(missing_crop, self.learning)

    def test_rejects_nonexistent_crop_path_and_invalid_field_name(self) -> None:
        """Fail clearly when the referenced crop or field metadata is invalid."""
        missing_file = self._correction()
        missing_file.crop_path = str(self.root / "missing.png")
        wrong_field = self._correction()
        wrong_field.field_name = "Comment"

        with self.assertRaisesRegex(FileNotFoundError, "Correction crop not found"):
            save_correction(missing_file, self.learning)
        with self.assertRaisesRegex(ValueError, "field_name must be W, L, or Weight"):
            save_correction(wrong_field, self.learning)

    def test_export_includes_csv_manifest_and_crop(self) -> None:
        """Bundle metadata and referenced cell image into one ZIP."""
        save_correction(self._correction(), self.learning)
        destination = self.root / "learning.zip"

        export_learning_data(destination, self.learning)

        with ZipFile(destination) as archive:
            names = archive.namelist()
        self.assertIn(CORRECTIONS_FILENAME, names)
        self.assertIn("manifest.json", names)
        self.assertTrue(any(name.startswith("crops/") for name in names))

    def test_export_rejects_non_zip_path_and_existing_destination(self) -> None:
        """Protect export callers from unsafe or ambiguous archive destinations."""
        save_correction(self._correction(), self.learning)
        existing = self.root / "existing.zip"
        existing.write_bytes(b"existing")

        with self.assertRaisesRegex(ValueError, "must use the .zip extension"):
            export_learning_data(self.root / "learning.txt", self.learning)
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            export_learning_data(existing, self.learning)

    def test_load_rejects_unexpected_header_and_invalid_row(self) -> None:
        """Reject corrupt correction CSV files instead of silently misreading them."""
        wrong_header = self.learning / CORRECTIONS_FILENAME
        wrong_header.write_text("bad,columns\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unexpected correction CSV columns"):
            load_corrections(self.learning)

        wrong_header.write_text(
            ",".join(
                [
                    "timestamp",
                    "source_image",
                    "mouse_id",
                    "field_name",
                    "original_prediction",
                    "corrected_value",
                    "crop_path",
                ]
            )
            + "\n"
            + "not-a-date,page.jpg,001,W,,1.25,"
            + str(self.crop)
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Invalid correction record"):
            load_corrections(self.learning)

    def test_locked_primary_csv_falls_back_to_pending_file(self) -> None:
        """Keep learning data when the main correction CSV is temporarily locked."""
        real_append = learning_store._append_correction_row

        def append_with_locked_primary(csv_path: Path, row: dict[str, str]) -> None:
            if csv_path.name == CORRECTIONS_FILENAME:
                raise PermissionError("locked")
            real_append(csv_path, row)

        with patch(
            "src.learning_store._append_correction_row",
            side_effect=append_with_locked_primary,
        ):
            self.assertTrue(save_correction(self._correction(), self.learning))

        self.assertFalse((self.learning / CORRECTIONS_FILENAME).exists())
        self.assertTrue((self.learning / PENDING_CORRECTIONS_FILENAME).is_file())
        loaded = load_corrections(self.learning)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].corrected_value, 0.0)

    def test_load_corrections_reads_primary_and_pending_files(self) -> None:
        """Merge both correction CSV files so fallback-saved labels still train OCR."""
        first = self._correction(original=None, corrected=1.25)
        second = self._correction(original=1.25, corrected=2.5)
        second.mouse_id = "002"
        first.timestamp = first.timestamp.replace(microsecond=1)
        second.timestamp = second.timestamp.replace(microsecond=2)

        save_correction(first, self.learning)
        pending = self.learning / PENDING_CORRECTIONS_FILENAME
        pending.write_text(
            ",".join(
                [
                    "timestamp",
                    "source_image",
                    "mouse_id",
                    "field_name",
                    "original_prediction",
                    "corrected_value",
                    "crop_path",
                ]
            )
            + "\n"
            + ",".join(
                [
                    second.timestamp.isoformat(),
                    second.source_image,
                    second.mouse_id,
                    second.field_name,
                    "1.25",
                    "2.50",
                    str(self.crop.resolve()),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        loaded = load_corrections(self.learning)

        self.assertEqual([record.mouse_id for record in loaded], ["001", "002"])
        self.assertEqual([record.corrected_value for record in loaded], [1.25, 2.5])

    def test_consolidate_learning_files_merges_primary_and_pending(self) -> None:
        """Collapse split learning CSV files back into one canonical file."""
        first = self._correction(original=None, corrected=1.25)
        second = self._correction(original=1.25, corrected=2.5)
        second.mouse_id = "002"
        save_correction(first, self.learning)
        pending = self.learning / PENDING_CORRECTIONS_FILENAME
        pending.write_text(
            ",".join(
                [
                    "timestamp",
                    "source_image",
                    "mouse_id",
                    "field_name",
                    "original_prediction",
                    "corrected_value",
                    "crop_path",
                ]
            )
            + "\n"
            + ",".join(
                [
                    second.timestamp.isoformat(),
                    second.source_image,
                    second.mouse_id,
                    second.field_name,
                    "1.25",
                    "2.50",
                    str(self.crop.resolve()),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        self.assertTrue(consolidate_learning_files(self.learning))

        self.assertTrue((self.learning / CORRECTIONS_FILENAME).is_file())
        self.assertFalse((self.learning / PENDING_CORRECTIONS_FILENAME).exists())
        loaded = load_corrections(self.learning)
        self.assertEqual([record.mouse_id for record in loaded], ["001", "002"])

    def test_consolidate_renames_pending_when_it_is_the_only_file(self) -> None:
        """Normalize a lone pending file back to corrections.csv on startup."""
        pending = self.learning / PENDING_CORRECTIONS_FILENAME
        pending.write_text(
            ",".join(
                [
                    "timestamp",
                    "source_image",
                    "mouse_id",
                    "field_name",
                    "original_prediction",
                    "corrected_value",
                    "crop_path",
                ]
            )
            + "\n"
            + ",".join(
                [
                    self._correction().timestamp.isoformat(),
                    "page.jpg",
                    "001",
                    "W",
                    "",
                    "0.00",
                    str(self.crop.resolve()),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        self.assertTrue(consolidate_learning_files(self.learning))

        self.assertTrue((self.learning / CORRECTIONS_FILENAME).is_file())
        self.assertFalse(pending.exists())

    def test_run_reset_preserves_csv_and_full_reset_removes_it(self) -> None:
        """Separate ephemeral one-run state from persisted learning history."""
        save_correction(self._correction(), self.learning)
        self.assertEqual(len(current_run_corrections()), 1)

        self.assertEqual(reset_learning_for_current_run_only(), 1)
        self.assertTrue((self.learning / CORRECTIONS_FILENAME).is_file())
        self.assertEqual(current_run_corrections(), [])

        self.assertEqual(reset_learning_data(self.learning), 1)
        self.assertEqual(list(self.learning.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
