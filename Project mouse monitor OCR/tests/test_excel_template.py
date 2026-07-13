"""Tests for read-only Excel template inspection."""

import unittest
from io import BytesIO
from zipfile import ZipFile

from openpyxl import Workbook

from src.excel_template import (
    DuplicateMouseIDError,
    build_mouse_id_mapping,
    validate_xlsx_upload,
)


class ExcelTemplateTests(unittest.TestCase):
    """Verify stable row mapping, empty rows, and duplicate detection."""

    def test_maps_ids_to_original_rows_without_compressing_gaps(self) -> None:
        """Keep actual Excel row numbers when mouse rows are separated by blanks."""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet["A1"] = "Cage"
        sheet["B2"] = "001"
        sheet["B5"] = 27.0
        sheet["M8"] = "existing formula area"
        existing_cell_count = len(sheet._cells)

        metadata = build_mouse_id_mapping(workbook, "Sheet1", "B")

        self.assertEqual(metadata.mouse_id_to_row, {"001": 2, "27": 5})
        self.assertEqual(metadata.mapped_mouse_count, 2)
        self.assertEqual(metadata.first_used_row, 1)
        self.assertEqual(metadata.last_used_row, 8)
        self.assertEqual(len(sheet._cells), existing_cell_count)

    def test_ignores_blank_ids_and_rejects_duplicates(self) -> None:
        """Ignore whitespace-only cells and identify both duplicate source rows."""
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        sheet["B2"] = "  "
        sheet["B4"] = 12
        sheet["B9"] = 12.0

        with self.assertRaisesRegex(DuplicateMouseIDError, "rows 4 and 9"):
            build_mouse_id_mapping(workbook, "Sheet1", "B")

    def test_rejects_non_xlsx_upload_content(self) -> None:
        """Do not persist a renamed or malformed workbook upload."""
        with self.assertRaisesRegex(ValueError, "not a valid XLSX"):
            validate_xlsx_upload(b"not a zip")

    def test_accepts_minimal_required_xlsx_zip_structure(self) -> None:
        """Recognize required XLSX members before openpyxl performs full parsing."""
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "content")
            archive.writestr("xl/workbook.xml", "workbook")

        validate_xlsx_upload(buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
