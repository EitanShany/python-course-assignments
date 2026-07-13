from pathlib import Path

import pandas as pd


def export_qc_report(qc_df: pd.DataFrame, output_dir: str | Path) -> Path:
    """Export the QC report to qc_report.csv."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    output_path = path / "qc_report.csv"
    qc_df.to_csv(output_path, index=False)
    return output_path


def export_exploratory_report(report_df: pd.DataFrame, output_dir: str | Path) -> Path:
    """Export exploratory candidate paths to exploratory_candidate_paths.csv."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    output_path = path / "exploratory_candidate_paths.csv"
    report_df.to_csv(output_path, index=False)
    return output_path


def export_sample_level_results(results_df: pd.DataFrame, output_dir: str | Path) -> Path:
    """Export mock sample-level results to sample_level_results.csv."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    output_path = path / "sample_level_results.csv"
    results_df.to_csv(output_path, index=False)
    return output_path


def export_analysis_workbook(
    output_dir: str | Path,
    qc_df: pd.DataFrame,
    exploratory_df: pd.DataFrame,
) -> Path:
    """Export QC and exploratory reports to one Excel workbook."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    output_path = path / "immunoflow_analysis_output.xlsx"
    with pd.ExcelWriter(output_path) as writer:
        qc_df.to_excel(writer, sheet_name="QC_Report", index=False)
        exploratory_df.to_excel(writer, sheet_name="Exploratory_Candidate_Paths", index=False)

    return output_path


def export_results(
    output_dir: str | Path,
    validation_messages: list[str],
    qc_messages: list[str],
    exploratory_paths: list[dict[str, str]],
) -> dict[str, Path]:
    """Export milestone reports to CSV files."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    outputs = {
        "validation": path / "validation_report.csv",
        "qc": path / "qc_report.csv",
        "exploratory": path / "exploratory_paths.csv",
    }

    pd.DataFrame({"Message": validation_messages}).to_csv(outputs["validation"], index=False)
    pd.DataFrame({"Message": qc_messages}).to_csv(outputs["qc"], index=False)
    pd.DataFrame(exploratory_paths).to_csv(outputs["exploratory"], index=False)

    return outputs
