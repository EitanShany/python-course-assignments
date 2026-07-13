"""Tests for central application configuration."""

import json
from pathlib import Path
import tempfile
import unittest

from src.config import Config


class ConfigTests(unittest.TestCase):
    """Verify settings parsing and required-path errors."""

    def _project(self, include_template: bool = True) -> tuple[tempfile.TemporaryDirectory, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "config").mkdir()
        (root / "data" / "templates").mkdir(parents=True)
        (root / "data" / "output").mkdir()
        (root / "data" / "input_images").mkdir()
        if include_template:
            (root / "data" / "templates" / "Book1.xlsx").touch()
        source = Path(__file__).resolve().parents[1] / "config" / "settings.json"
        settings = json.loads(source.read_text(encoding="utf-8"))
        settings_path = root / "config" / "settings.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        return temporary, settings_path

    def test_loads_expected_excel_mapping(self) -> None:
        """Resolve paths and retain the required ID and output columns."""
        temporary, settings_path = self._project()
        self.addCleanup(temporary.cleanup)

        config = Config.load(settings_path)

        self.assertEqual(config.mouse_id_column, "B")
        self.assertEqual(config.output_columns, {"W": "K", "L": "L", "Weight": "M"})
        self.assertEqual(config.valid_ranges["Weight"], (0.0, 40.0))
        self.assertTrue(config.zero_is_valid)
        self.assertEqual(config.excel_number_format, "0.00")

    def test_missing_template_has_clear_error(self) -> None:
        """Reject a configuration whose required workbook is absent."""
        temporary, settings_path = self._project(include_template=False)
        self.addCleanup(temporary.cleanup)

        with self.assertRaisesRegex(FileNotFoundError, "Excel template not found"):
            Config.load(settings_path)


if __name__ == "__main__":
    unittest.main()
