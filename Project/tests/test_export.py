import pandas as pd

from immunoflow_discovery_analyzer.export import (
    export_analysis_workbook,
    export_exploratory_report,
    export_qc_report,
    export_results,
    export_sample_level_results,
)


def test_export_qc_report_writes_qc_report_csv(tmp_path):
    qc_df = pd.DataFrame(
        [
            {
                "Severity": "ERROR",
                "Check": "Missing_FCS_File",
                "Message": "Missing file",
                "Affected_Item": "sample1.fcs",
            }
        ]
    )

    output_path = export_qc_report(qc_df, tmp_path)

    assert output_path == tmp_path / "qc_report.csv"
    saved = pd.read_csv(output_path)
    assert saved.loc[0, "Check"] == "Missing_FCS_File"


def test_export_exploratory_report_writes_candidate_paths_csv(tmp_path):
    report_df = pd.DataFrame(
        [
            {
                "Search_ID": "Search_1",
                "Starting_Population": "CD8+",
                "Exploratory_Path": "CD8+ -> CD44+",
                "Result_Type": "Exploratory",
            }
        ]
    )

    output_path = export_exploratory_report(report_df, tmp_path)

    assert output_path == tmp_path / "exploratory_candidate_paths.csv"
    saved = pd.read_csv(output_path)
    assert saved.loc[0, "Exploratory_Path"] == "CD8+ -> CD44+"


def test_export_analysis_workbook_writes_expected_sheets(tmp_path):
    qc_df = pd.DataFrame(
        [
            {
                "Severity": "ERROR",
                "Check": "Missing_FCS_File",
                "Message": "Missing file",
                "Affected_Item": "sample1.fcs",
            }
        ]
    )
    exploratory_df = pd.DataFrame(
        [
            {
                "Search_ID": "Search_1",
                "Starting_Population": "CD8+",
                "Exploratory_Path": "CD8+ -> CD44+",
                "Result_Type": "Exploratory",
            }
        ]
    )

    output_path = export_analysis_workbook(tmp_path, qc_df, exploratory_df)

    assert output_path == tmp_path / "immunoflow_analysis_output.xlsx"
    workbook = pd.read_excel(output_path, sheet_name=None)
    assert set(workbook) == {"QC_Report", "Exploratory_Candidate_Paths"}
    assert workbook["QC_Report"].loc[0, "Check"] == "Missing_FCS_File"
    assert workbook["Exploratory_Candidate_Paths"].loc[0, "Result_Type"] == "Exploratory"


def test_export_sample_level_results_writes_csv(tmp_path):
    results_df = pd.DataFrame(
        [
            {
                "Sample_ID": "S1",
                "FCS_File": "sample1.fcs",
                "Search_ID": "Search_1",
                "Starting_Population": "CD8+",
                "Exploratory_Path": "CD8+ -> CD44+",
                "Count": 100,
                "Percent_of_Parent": 12.5,
                "Result_Type": "Exploratory",
            }
        ]
    )

    output_path = export_sample_level_results(results_df, tmp_path)

    assert output_path == tmp_path / "sample_level_results.csv"
    saved = pd.read_csv(output_path)
    assert saved.loc[0, "Count"] == 100


def test_export_results_legacy_function_writes_all_csv_files(tmp_path):
    outputs = export_results(
        tmp_path,
        validation_messages=["validation message"],
        qc_messages=["qc message"],
        exploratory_paths=[{"Path": "CD8+ -> CD44+"}],
    )

    assert set(outputs) == {"validation", "qc", "exploratory"}
    assert outputs["validation"].name == "validation_report.csv"
    assert outputs["qc"].exists()
    assert outputs["exploratory"].exists()
