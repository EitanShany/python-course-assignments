"""Regression tests for GUI data preparation and review highlighting."""

import unittest
import math
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook

from src.gui import (
    INTERNAL_COLUMNS,
    VISIBLE_COLUMNS,
    _config_with_writable_output_folder,
    _commit_review_rows,
    _has_uncommitted_review_changes,
    _highlight_review_row,
    _is_empty_export_slot,
    _missing,
    _normalize_review_dataframe,
    _row_export_issues,
    _save_gui_corrections,
    _set_warning_approval_state,
    _stage_uploaded_template,
    _unapproved_export_issues,
)
from src.config import Config
from src.review_model import ExtractedMeasurement


class GuiTests(unittest.TestCase):
    """Verify multi-image mock rows and visual severity colors."""

    def test_highlight_colors_cover_required_conditions(self) -> None:
        """Assign colors only to the problematic field or warning cell."""
        base = {
            "W": 1.0,
            "L": 2.0,
            "Weight": 20.0,
            "warnings": "",
            "comment_detected": False,
            "crossed_out_or_side_note_detected": False,
        }
        missing_w = _highlight_review_row(pd.Series({**base, "W": None}))
        missing_weight = _highlight_review_row(pd.Series({**base, "Weight": None}))
        outside_range = _highlight_review_row(pd.Series({**base, "L": 21.0}))
        comment = _highlight_review_row(
            pd.Series({**base, "comment_detected": True})
        )

        columns = list(base)
        self.assertIn("#ffd6d6", missing_w[columns.index("W")])
        self.assertEqual(sum(bool(style) for style in missing_w), 1)
        self.assertIn("#fff3bf", missing_weight[columns.index("Weight")])
        self.assertEqual(sum(bool(style) for style in missing_weight), 1)
        self.assertIn("#ffe1bf", outside_range[columns.index("L")])
        self.assertEqual(sum(bool(style) for style in outside_range), 1)
        self.assertIn("#eadcff", comment[columns.index("warnings")])

    def test_negative_value_uses_error_color_and_zero_is_unmarked(self) -> None:
        """Use a distinct error color for negatives while preserving valid zero."""
        row = pd.Series({"W": -0.01, "L": 0.0, "Weight": 0.0})

        styles = _highlight_review_row(row)

        self.assertIn("#ff9f9f", styles[row.index.get_loc("W")])
        self.assertEqual(styles[row.index.get_loc("L")], "")
        self.assertEqual(styles[row.index.get_loc("Weight")], "")

    def test_export_blockers_require_only_specific_warning_approval(self) -> None:
        """Allow clean and missing-Weight rows but block required field warnings."""
        clean = ExtractedMeasurement(
            source_image="page.jpg", mouse_id="1", W=0, L=0, Weight=0
        )
        missing_weight = ExtractedMeasurement(
            source_image="page.jpg", mouse_id="2", W=1, L=2, Weight=None
        )
        missing_w = ExtractedMeasurement(
            source_image="page.jpg", mouse_id="3", W=None, L=2, Weight=20
        )
        excessive_weight = ExtractedMeasurement(
            source_image="page.jpg", mouse_id="4", W=1, L=2, Weight=41
        )

        issues = _unapproved_export_issues(
            [clean, missing_weight, missing_w, excessive_weight]
        )

        self.assertEqual(len(issues), 2)
        self.assertIn("Mouse ID 3: W is missing", issues)
        self.assertIn("Mouse ID 4: Weight is above 40.00 (41.00)", issues)

        missing_w.approved = True
        excessive_weight.approved = True
        self.assertEqual(
            _unapproved_export_issues(
                [clean, missing_weight, missing_w, excessive_weight]
            ),
            [],
        )

        non_finite = ExtractedMeasurement(
            source_image="page.jpg",
            mouse_id="5",
            W=math.inf,
            L=2,
            Weight=20,
            approved=True,
        )
        self.assertIn(
            "W is not a finite number",
            _unapproved_export_issues([non_finite])[0],
        )

    def test_only_blank_values_are_missing(self) -> None:
        """Treat blank strings and None as missing, but never numeric zero."""
        self.assertTrue(_missing(None))
        self.assertTrue(_missing(""))
        self.assertTrue(_missing("   "))
        self.assertFalse(_missing(0))
        self.assertFalse(_missing(0.0))

    def test_draft_edits_do_not_change_export_rows_until_commit(self) -> None:
        """Keep typed corrections separate from the export table until requested."""
        export_rows, _, _ = _commit_review_rows(
            pd.DataFrame([self._review_row(w_value=None)])
        )
        draft_rows = export_rows.copy()
        draft_rows.loc[0, "W"] = 1.25

        self.assertTrue(_has_uncommitted_review_changes(draft_rows, export_rows))
        self.assertIsNone(export_rows.loc[0, "W"])

        committed_rows, _, _ = _commit_review_rows(draft_rows)

        self.assertFalse(_has_uncommitted_review_changes(committed_rows, committed_rows))
        self.assertEqual(committed_rows.loc[0, "W"], 1.25)
        self.assertFalse(
            any(
                "W is missing" in warning
                for warning in str(committed_rows.loc[0, "warnings"]).split(" | ")
            )
        )

    def test_visible_columns_do_not_show_inline_approval_checkbox(self) -> None:
        """Keep row-approval controls outside the editable review table."""
        self.assertNotIn("approved", VISIBLE_COLUMNS)

    def test_normalize_review_dataframe_drops_stale_approved_column(self) -> None:
        """Remove leftover columns from older GUI sessions when restoring state."""
        stale = pd.DataFrame(
            [
                {
                    **self._review_row(w_value=1.25),
                    "approved": True,
                }
            ]
        )

        normalized = _normalize_review_dataframe(stale)

        self.assertNotIn("approved", normalized.columns)
        self.assertEqual(
            list(normalized.columns),
            VISIBLE_COLUMNS + INTERNAL_COLUMNS,
        )

    def test_empty_fixed_slot_does_not_need_export_approval(self) -> None:
        """Do not ask for approval for an intentionally empty cage slot."""
        empty_slot = ExtractedMeasurement(
            source_image="page.jpg",
            cage_number="1",
            mouse_id=None,
            W=None,
            L=None,
            Weight=None,
            requires_manual_review=False,
            warnings=[],
        )

        self.assertTrue(_is_empty_export_slot(empty_slot))
        self.assertEqual(_row_export_issues(empty_slot), [])
        self.assertEqual(_unapproved_export_issues([empty_slot]), [])

    def test_bulk_warning_approval_state_sets_each_row_key(self) -> None:
        """Approve or disapprove all displayed warning rows through session state."""
        rows = [
            {
                "source_image": "page.jpg",
                "cage_number": "1",
                "page_row": 1,
                "mouse_id": "1",
            },
            {
                "source_image": "page.jpg",
                "cage_number": "1",
                "page_row": 2,
                "mouse_id": "2",
            },
        ]
        fake_session_state = {}

        with patch("src.gui.st.session_state", fake_session_state):
            _set_warning_approval_state(rows, True)
            self.assertTrue(all(fake_session_state.values()))

            _set_warning_approval_state(rows, False)
            self.assertFalse(any(fake_session_state.values()))

    def test_learning_save_permission_error_shows_warning_without_crashing(self) -> None:
        """Warn the reviewer when learning storage is locked instead of crashing."""
        rows = pd.DataFrame([self._review_row(w_value=1.25)])
        fake_session_state = SimpleNamespace(saved_correction_keys=set())

        with (
            patch("src.gui.save_correction", side_effect=PermissionError("locked")),
            patch("src.gui.st.session_state", fake_session_state),
            patch("src.gui.st.warning") as warning_mock,
        ):
            _save_gui_corrections(rows)

        warning_mock.assert_called_once()
        self.assertEqual(fake_session_state.saved_correction_keys, set())

    def test_stage_uploaded_template_falls_back_to_temp_when_templates_folder_is_locked(self) -> None:
        """Use a temp staging folder when data/templates is not writable."""
        upload = SimpleNamespace(
            name="Sample.xlsx",
            getvalue=lambda: self._xlsx_bytes(),
        )

        with patch("src.gui._write_uploaded_template_copy", side_effect=[PermissionError("locked"), None]):
            destination, warning = _stage_uploaded_template(upload)

        self.assertIn("temporary folder", warning or "")
        self.assertEqual(destination.parent.name, "templates")
        self.assertEqual(destination.name, "uploaded_Sample.xlsx")

    def test_export_falls_back_to_temp_output_folder_when_project_output_is_locked(self) -> None:
        """Switch export writes to a temp folder when data/output is not writable."""
        config = Config.load()

        with patch("src.gui._folder_is_writable", return_value=False):
            updated, warning = _config_with_writable_output_folder(config)

        self.assertNotEqual(updated.output_folder, config.output_folder)
        self.assertEqual(updated.output_folder.name, "output")
        self.assertIn("temporary folder", warning or "")

    def test_export_uses_project_output_folder_when_it_is_writable(self) -> None:
        """Keep the configured output folder when no permission problem exists."""
        config = Config.load()

        with patch("src.gui._folder_is_writable", return_value=True):
            updated, warning = _config_with_writable_output_folder(config)

        self.assertEqual(updated.output_folder, config.output_folder)
        self.assertIsNone(warning)

    @staticmethod
    def _review_row(w_value: float | None) -> dict[str, object]:
        """Create one complete GUI row fixture with stable hidden columns."""
        row = {column: None for column in VISIBLE_COLUMNS + INTERNAL_COLUMNS}
        row.update(
            {
                "source_image": "page.jpg",
                "cage_number": "1",
                "mouse_id": "001",
                "ear_marking": None,
                "W": w_value,
                "L": 2.0,
                "Weight": 20.0,
                "warnings": "",
                "requires_manual_review": False,
                "comment_detected": False,
                "crossed_out_or_side_note_detected": False,
                "page_row": 1,
                "original_W": None,
                "original_L": 2.0,
                "original_Weight": 20.0,
                "crop_W": "w.png",
                "crop_L": "l.png",
                "crop_Weight": "weight.png",
            }
        )
        return row

    @staticmethod
    def _xlsx_bytes() -> bytes:
        """Create a tiny valid XLSX payload for template-upload tests."""
        workbook = Workbook()
        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
