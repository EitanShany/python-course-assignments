import pandas as pd

from immunoflow_discovery_analyzer.flowkit_adapter import FcsParameterReadResult
from immunoflow_discovery_analyzer.config import REQUIRED_EXCEL_SHEETS
from immunoflow_discovery_analyzer.qc import QC_COLUMNS, run_basic_qc, run_qc_checks


def _valid_sheets():
    return {
        "Experiment_Info": pd.DataFrame([{"Key": "Experiment_ID", "Value": "EXP-1"}]),
        "Acquisition_Processing": pd.DataFrame(
            [{"Acquisition_Mode": "Spectral", "Preprocessing_Status": "Unmixed"}]
        ),
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
                    "Search_ID": "Search-1",
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


def test_run_basic_qc_returns_expected_columns_for_clean_inputs(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.get_fcs_parameters",
        lambda _file_path: FcsParameterReadResult(parameters={"CD8-A"}),
    )
    fcs_files = pd.DataFrame([{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}])

    report = run_basic_qc(_valid_sheets(), fcs_files)

    assert list(report.columns) == QC_COLUMNS
    assert report.empty


def test_run_basic_qc_reports_missing_sheet_and_required_column(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.get_fcs_parameters",
        lambda _file_path: FcsParameterReadResult(parameters={"CD8-A"}),
    )
    sheets = _valid_sheets()
    del sheets["Marker_Gates"]
    sheets["Plate_Map"] = sheets["Plate_Map"].drop(columns=["Treatment"])

    report = run_basic_qc(sheets, [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}])

    assert set(report["Check"]) == {"Missing_Required_Sheet", "Missing_Required_Column"}
    assert "Marker_Gates" in report["Affected_Item"].tolist()
    assert "Plate_Map.Treatment" in report["Affected_Item"].tolist()


def test_run_basic_qc_reports_missing_and_extra_fcs_files():
    sheets = _valid_sheets()
    sheets["Plate_Map"].loc[0, "FCS_File"] = "missing.fcs"
    fcs_files = [{"file_name": "extra.fcs", "file_path": "data/extra.fcs"}]

    report = run_basic_qc(sheets, fcs_files)

    assert "Missing_FCS_File" in report["Check"].tolist()
    assert "Extra_FCS_File" in report["Check"].tolist()
    assert "missing.fcs" in report["Affected_Item"].tolist()
    assert "extra.fcs" in report["Affected_Item"].tolist()


def test_run_basic_qc_reports_missing_plate_map_values_and_duplicates():
    sheets = _valid_sheets()
    sheets["Plate_Map"] = pd.DataFrame(
        [
            {
                "Well": "A01",
                "Sample_ID": "S1",
                "Subject_ID": "M1",
                "Treatment": "",
                "Tissue": "Tumor",
                "Replicate": 1,
                "FCS_File": "sample1.fcs",
            },
            {
                "Well": "A01",
                "Sample_ID": "S1",
                "Subject_ID": "M2",
                "Treatment": "Treatment",
                "Tissue": "Tumor",
                "Replicate": 1,
                "FCS_File": "sample2.fcs",
            },
            {
                "Well": "A03",
                "Sample_ID": "",
                "Subject_ID": "M3",
                "Treatment": "Treatment",
                "Tissue": "Tumor",
                "Replicate": 1,
                "FCS_File": "sample3.fcs",
            },
        ]
    )
    fcs_files = [
        {"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"},
        {"file_name": "sample2.fcs", "file_path": "data/sample2.fcs"},
        {"file_name": "sample3.fcs", "file_path": "data/sample3.fcs"},
    ]

    report = run_basic_qc(sheets, fcs_files)

    checks = report["Check"].tolist()
    assert "Missing_Treatment" in checks
    assert "Missing_Sample_ID" in checks
    assert "Duplicate_Well" in checks
    assert "Duplicate_Sample_ID" in checks


def test_run_basic_qc_reports_spectral_data_not_unmixed():
    sheets = _valid_sheets()
    sheets["Acquisition_Processing"] = pd.DataFrame(
        [{"Acquisition_Mode": "Spectral", "Preprocessing_Status": "Compensated"}]
    )

    report = run_basic_qc(sheets, [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}])

    assert "Spectral_Not_Unmixed" in report["Check"].tolist()


def test_run_basic_qc_skips_parameter_check_when_panel_column_is_missing():
    sheets = _valid_sheets()
    sheets["Panel_Definition"] = pd.DataFrame([{"Marker": "CD8"}])

    report = run_basic_qc(
        sheets,
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
    )

    assert "Missing_FCS_Parameter" not in report["Check"].tolist()
    assert "FCS_Parameter_Check_Skipped" not in report["Check"].tolist()


def test_run_basic_qc_skips_parameter_check_when_required_parameters_are_empty():
    sheets = _valid_sheets()
    sheets["Panel_Definition"] = pd.DataFrame([{"Parameter_in_FCS": ""}])

    report = run_basic_qc(
        sheets,
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
    )

    assert "Missing_FCS_Parameter" not in report["Check"].tolist()


def test_run_basic_qc_does_not_crash_when_duplicate_columns_are_missing():
    sheets = _valid_sheets()
    sheets["Plate_Map"] = pd.DataFrame(
        [{"Sample_ID": "S1", "Treatment": "Control", "FCS_File": "sample1.fcs"}]
    )

    report = run_basic_qc(
        sheets,
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
    )

    assert "Duplicate_Well" not in report["Check"].tolist()


def test_run_basic_qc_reports_missing_required_fcs_parameter(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.get_fcs_parameters",
        lambda _file_path: FcsParameterReadResult(parameters={"FSC-A"}),
    )

    report = run_basic_qc(
        _valid_sheets(),
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
    )

    assert "Missing_FCS_Parameter" in report["Check"].tolist()
    assert "sample1.fcs:CD8-A" in report["Affected_Item"].tolist()


def test_run_basic_qc_warns_when_flowkit_parameter_check_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.get_fcs_parameters",
        lambda _file_path: FcsParameterReadResult(
            parameters=set(),
            warning="FlowKit is not installed; FCS parameter validation was skipped in mock mode.",
        ),
    )

    report = run_basic_qc(
        _valid_sheets(),
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
    )

    assert "FCS_Parameter_Check_Skipped" in report["Check"].tolist()
    assert "WARNING" in report["Severity"].tolist()


def test_run_qc_checks_wrapper_returns_messages():
    report_messages = run_qc_checks(
        {"Experiment_Info": pd.DataFrame()},
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
    )

    assert any("Missing required Excel sheet" in message for message in report_messages)


def test_run_basic_qc_reports_flowjo_sample_mismatches_and_duplicates(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.get_fcs_parameters",
        lambda _file_path: FcsParameterReadResult(parameters={"CD8-A"}),
    )
    flowjo_results = pd.DataFrame(
        [
            {
                "Sample_ID": "S1",
                "Exploratory_Path": "CD8+",
                "Count": 100,
                "Percent_of_Parent": 10,
            },
            {
                "Sample_ID": "S1",
                "Exploratory_Path": "CD8+",
                "Count": 100,
                "Percent_of_Parent": 10,
            },
            {
                "Sample_ID": "S-extra",
                "Exploratory_Path": "CD8+",
                "Count": 100,
                "Percent_of_Parent": 10,
            },
        ]
    )

    report = run_basic_qc(
        _valid_sheets(),
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
        flowjo_results_df=flowjo_results,
    )

    assert "Duplicate_FlowJo_Result" in report["Check"].tolist()
    assert "Extra_FlowJo_Result" in report["Check"].tolist()


def test_run_basic_qc_reports_missing_and_invalid_flowjo_values(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.get_fcs_parameters",
        lambda _file_path: FcsParameterReadResult(parameters={"CD8-A"}),
    )
    flowjo_results = pd.DataFrame(
        [
            {
                "Sample_ID": "S2",
                "Exploratory_Path": "CD8+",
                "Count": -1,
                "Percent_of_Parent": 120,
            }
        ]
    )

    report = run_basic_qc(
        _valid_sheets(),
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
        flowjo_results_df=flowjo_results,
    )

    checks = report["Check"].tolist()
    assert "Missing_FlowJo_Result" in checks
    assert "Extra_FlowJo_Result" in checks
    assert "Invalid_FlowJo_Count" in checks
    assert "Invalid_FlowJo_Percent_of_Parent" in checks


def test_run_basic_qc_warns_when_flowjo_results_are_empty():
    report = run_basic_qc(
        _valid_sheets(),
        [{"file_name": "sample1.fcs", "file_path": "data/sample1.fcs"}],
        flowjo_results_df=pd.DataFrame(),
    )

    assert "FlowJo_Results_Empty" in report["Check"].tolist()
