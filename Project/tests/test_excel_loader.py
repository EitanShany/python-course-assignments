import pandas as pd
import pytest

from immunoflow_discovery_analyzer.config import REQUIRED_EXCEL_SHEETS
from immunoflow_discovery_analyzer.excel_loader import (
    load_excel_workbook,
    load_workbook_sheets,
    validate_excel_workbook,
    validate_required_columns,
)


def _valid_workbook():
    return {
        "Experiment_Info": pd.DataFrame([{"Key": "Experiment_ID", "Value": "EXP-1"}]),
        "Acquisition_Processing": pd.DataFrame([{"Acquisition_Mode": "Conventional"}]),
        "Panel_Definition": pd.DataFrame(
            [
                {
                    "Parameter_in_FCS": "CD8-A",
                    "Fluorophore": "APC",
                    "Marker": "CD8",
                    "Marker_role": "Lineage",
                }
            ]
        ),
        "Plate_Map": pd.DataFrame(
            [
                {
                    "Well": "A01",
                    "Sample_ID": "S1",
                    "Subject_ID": "M1",
                    "Treatment": "Control",
                    "Tissue": "Tumor",
                    "Replicate": 1,
                    "FCS_File": "sample1.fcs",
                }
            ]
        ),
        "Gating_Workflow": pd.DataFrame(
            [
                {
                    "Gate_Name": "CD8+",
                    "Parent_Gate": "CD3+",
                    "Gate_Type": "threshold",
                    "X_Parameter": "CD8-A",
                    "Y_Parameter": "",
                    "Analysis_Role": "Closed",
                }
            ]
        ),
        "Marker_Gates": pd.DataFrame(
            [
                {
                    "Marker": "PD-1",
                    "Positive_Gate_Name": "PD-1+",
                    "Negative_Gate_Name": "PD-1-",
                    "Parent_Population": "CD8+",
                    "Gate_Source": "template",
                }
            ]
        ),
        "Exploratory_Search": pd.DataFrame(
            [
                {
                    "Search_ID": "S1",
                    "Starting_Population": "CD8+",
                    "Compare_Groups": "Treatment vs Control",
                    "Reference_Group": "Control",
                    "Minimum_Events": 100,
                }
            ]
        ),
        "Planned_Comparisons": pd.DataFrame(
            [
                {
                    "Comparison_ID": "C1",
                    "Population": "CD8+",
                    "Parent_Population": "CD3+",
                    "Treatment_Group": "Treatment",
                    "Reference_Group": "Control",
                    "Metric": "Frequency",
                }
            ]
        ),
    }


def test_validate_excel_workbook_accepts_required_structure():
    messages = validate_excel_workbook(_valid_workbook())

    assert messages == []


def test_validate_excel_workbook_reports_missing_sheet():
    workbook = {"Experiment_Info": pd.DataFrame()}

    messages = validate_excel_workbook(workbook)

    assert "ERROR: Missing required sheet: Plate_Map" in messages
    assert messages.count("ERROR: Missing required sheet: Plate_Map") == 1


def test_validate_required_columns_returns_errors_for_missing_columns():
    workbook = _valid_workbook()
    workbook["Panel_Definition"] = workbook["Panel_Definition"].drop(columns=["Marker_role"])
    workbook["Plate_Map"] = workbook["Plate_Map"].drop(columns=["Subject_ID"])

    errors = validate_required_columns(workbook)

    assert "ERROR: Panel_Definition is missing required column: Marker_role" in errors
    assert "ERROR: Plate_Map is missing required column: Subject_ID" in errors


def test_load_workbook_sheets_returns_required_sheet_dictionary(tmp_path):
    excel_path = tmp_path / "template.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        for sheet_name in REQUIRED_EXCEL_SHEETS:
            pd.DataFrame([{"Value": sheet_name}]).to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

    workbook = load_workbook_sheets(excel_path)

    assert list(workbook.keys()) == REQUIRED_EXCEL_SHEETS
    assert workbook["Experiment_Info"].loc[0, "Value"] == "Experiment_Info"


def test_load_workbook_sheets_raises_value_error_for_missing_sheet(tmp_path):
    excel_path = tmp_path / "template.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame([{"Value": "only one sheet"}]).to_excel(
            writer,
            sheet_name="Experiment_Info",
            index=False,
        )

    with pytest.raises(ValueError, match="missing required sheet"):
        load_workbook_sheets(excel_path)


def test_load_workbook_sheets_raises_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing.xlsx"

    with pytest.raises(FileNotFoundError, match="Excel workbook was not found"):
        load_workbook_sheets(missing_path)


def test_load_workbook_sheets_raises_for_invalid_extension(tmp_path):
    text_path = tmp_path / "template.txt"
    text_path.write_text("not excel", encoding="utf-8")

    with pytest.raises(ValueError, match="Excel workbook must be"):
        load_workbook_sheets(text_path)


def test_load_excel_workbook_wrapper_calls_loader(tmp_path):
    excel_path = tmp_path / "template.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        for sheet_name in REQUIRED_EXCEL_SHEETS:
            pd.DataFrame([{"Value": sheet_name}]).to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )

    workbook = load_excel_workbook(excel_path)

    assert list(workbook.keys()) == REQUIRED_EXCEL_SHEETS
