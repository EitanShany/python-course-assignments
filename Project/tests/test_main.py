import runpy
from pathlib import Path

import pandas as pd
import pytest


def test_package_main_calls_cli_main(monkeypatch):
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.cli.main",
        lambda: 7,
    )

    with pytest.raises(SystemExit) as error:
        runpy.run_module("immunoflow_discovery_analyzer.__main__", run_name="__main__")

    assert error.value.code == 7


@pytest.mark.filterwarnings("ignore:.*immunoflow_discovery_analyzer.cli.*:RuntimeWarning")
def test_cli_module_main_guard_runs_main(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli.py",
            "--fcs-dir",
            str(tmp_path / "fcs"),
            "--excel",
            str(tmp_path / "template.xlsx"),
            "--output-dir",
            str(tmp_path / "results"),
        ],
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.excel_loader.load_workbook_sheets",
        lambda _path: {
            "Exploratory_Search": pd.DataFrame(),
            "Marker_Gates": pd.DataFrame(),
            "Plate_Map": pd.DataFrame(),
        },
    )
    monkeypatch.setattr("immunoflow_discovery_analyzer.fcs_scanner.scan_fcs_files", lambda _path: [])
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.qc.run_basic_qc",
        lambda _sheets, _fcs, flowjo_results_df=None: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.exploratory.create_mock_exploratory_report",
        lambda _search, _markers: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.results.create_mock_sample_level_results",
        lambda _plate_map, _exploratory: pd.DataFrame(),
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.export.export_qc_report",
        lambda _df, output_dir: Path(output_dir) / "qc_report.csv",
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.export.export_exploratory_report",
        lambda _df, output_dir: Path(output_dir) / "exploratory_candidate_paths.csv",
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.export.export_sample_level_results",
        lambda _df, output_dir: Path(output_dir) / "sample_level_results.csv",
    )
    monkeypatch.setattr(
        "immunoflow_discovery_analyzer.export.export_analysis_workbook",
        lambda output_dir, _qc, _exploratory: Path(output_dir) / "immunoflow_analysis_output.xlsx",
    )

    with pytest.raises(SystemExit) as error:
        runpy.run_module("immunoflow_discovery_analyzer.cli", run_name="__main__")

    assert error.value.code == 0
