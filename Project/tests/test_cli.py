import pandas as pd

from immunoflow_discovery_analyzer.cli import main
from immunoflow_discovery_analyzer.config import REQUIRED_COLUMNS, REQUIRED_EXCEL_SHEETS

from fcs_test_helpers import write_test_fcs


def test_cli_exports_qc_and_exploratory_reports(tmp_path):
    fcs_dir = tmp_path / "fcs"
    fcs_dir.mkdir()
    (fcs_dir / "sample1.fcs").write_text("content is ignored", encoding="utf-8")

    excel_path = tmp_path / "template.xlsx"
    _write_minimal_workbook(excel_path)

    output_dir = tmp_path / "results"
    exit_code = main(
        [
            "--fcs-dir",
            str(fcs_dir),
            "--excel",
            str(excel_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "qc_report.csv").exists()
    assert (output_dir / "exploratory_candidate_paths.csv").exists()
    assert (output_dir / "sample_level_results.csv").exists()
    assert (output_dir / "immunoflow_analysis_output.xlsx").exists()


def test_cli_uses_flowjo_export_for_sample_level_results(tmp_path):
    fcs_dir = tmp_path / "fcs"
    fcs_dir.mkdir()
    (fcs_dir / "sample1.fcs").write_text("content is ignored", encoding="utf-8")

    excel_path = tmp_path / "template.xlsx"
    _write_minimal_workbook(excel_path)

    flowjo_path = tmp_path / "flowjo.csv"
    pd.DataFrame(
        [
            {
                "Sample ID": "S1",
                "FCS File": "sample1.fcs",
                "Gate Name": "CD8+",
                "Events": 123,
                "% Parent": 12.3,
            }
        ]
    ).to_csv(flowjo_path, index=False)

    output_dir = tmp_path / "results"
    exit_code = main(
        [
            "--fcs-dir",
            str(fcs_dir),
            "--excel",
            str(excel_path),
            "--flowjo-export",
            str(flowjo_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    sample_results = pd.read_csv(output_dir / "sample_level_results.csv")

    assert exit_code == 0
    assert sample_results.loc[0, "Result_Type"] == "FlowJo"
    assert sample_results.loc[0, "Count"] == 123


def test_cli_can_export_simple_python_fcs_analysis(tmp_path):
    fcs_dir = tmp_path / "fcs"
    fcs_dir.mkdir()
    write_test_fcs(
        fcs_dir / "sample1.fcs",
        ["CD20", "pS6"],
        [
            [1.0, 5.0],
            [2.0, 10.0],
            [100.0, 50.0],
            [120.0, 60.0],
        ],
    )

    excel_path = tmp_path / "template.xlsx"
    _write_minimal_workbook(excel_path)

    output_dir = tmp_path / "results"
    exit_code = main(
        [
            "--fcs-dir",
            str(fcs_dir),
            "--excel",
            str(excel_path),
            "--output-dir",
            str(output_dir),
            "--analyze-fcs",
            "--gate-percentile",
            "50",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "fcs_sample_metrics.csv").exists()
    assert (output_dir / "fcs_group_comparison.csv").exists()


def _write_minimal_workbook(excel_path):
    with pd.ExcelWriter(excel_path) as writer:
        for sheet_name in REQUIRED_EXCEL_SHEETS:
            columns = REQUIRED_COLUMNS.get(sheet_name, ["Key", "Value"])
            row = {column: _example_value(column) for column in columns}
            pd.DataFrame([row]).to_excel(writer, sheet_name=sheet_name, index=False)


def _example_value(column):
    values = {
        "FCS_File": "sample1.fcs",
        "Treatment": "Control",
        "Sample_ID": "S1",
        "Well": "A01",
        "Acquisition_Mode": "Conventional",
        "Preprocessing_Status": "Unmixed",
    }
    return values.get(column, "value")
