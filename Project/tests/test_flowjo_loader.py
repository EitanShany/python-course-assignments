import pandas as pd
import pytest

from immunoflow_discovery_analyzer.flowjo_loader import (
    convert_flowjo_to_sample_level_results,
    load_flowjo_results,
    normalize_flowjo_results,
)
from immunoflow_discovery_analyzer.results import SAMPLE_LEVEL_RESULT_COLUMNS


def test_normalize_flowjo_results_accepts_common_flowjo_aliases():
    flowjo = pd.DataFrame(
        [
            {
                "Sample ID": "S1",
                "FCS File": "sample1.fcs",
                "Gate Name": "CD8+",
                "Parent Gate": "CD3+",
                "Events": "1234",
                "% Parent": "12.5",
            }
        ]
    )

    normalized = normalize_flowjo_results(flowjo)

    assert normalized.loc[0, "Sample_ID"] == "S1"
    assert normalized.loc[0, "FCS_File"] == "sample1.fcs"
    assert normalized.loc[0, "Population"] == "CD8+"
    assert normalized.loc[0, "Parent_Population"] == "CD3+"
    assert normalized.loc[0, "Count"] == "1234"
    assert normalized.loc[0, "Percent_of_Parent"] == "12.5"


def test_normalize_flowjo_results_returns_empty_schema_for_empty_input():
    normalized = normalize_flowjo_results(pd.DataFrame())

    assert normalized.empty
    assert "Sample_ID" in normalized.columns
    assert "Parent_Population" in normalized.columns


def test_normalize_flowjo_results_raises_for_missing_required_columns():
    flowjo = pd.DataFrame([{"Sample ID": "S1", "Events": 100}])

    with pytest.raises(ValueError, match="Population"):
        normalize_flowjo_results(flowjo)


def test_convert_flowjo_to_sample_level_results_returns_project_schema():
    flowjo = pd.DataFrame(
        [
            {
                "Sample_ID": "S1",
                "FCS_File": "sample1.fcs",
                "Population": "CD8+",
                "Parent_Population": "CD3+",
                "Count": "100",
                "Percent_of_Parent": "25.5",
            }
        ]
    )

    results = convert_flowjo_to_sample_level_results(flowjo)

    assert list(results.columns) == SAMPLE_LEVEL_RESULT_COLUMNS
    assert results.loc[0, "Sample_ID"] == "S1"
    assert results.loc[0, "Exploratory_Path"] == "CD8+"
    assert results.loc[0, "Starting_Population"] == "CD3+"
    assert results.loc[0, "Count"] == 100
    assert results.loc[0, "Percent_of_Parent"] == 25.5
    assert results.loc[0, "Result_Type"] == "FlowJo"


def test_convert_flowjo_to_sample_level_results_keeps_bad_numeric_values_as_missing():
    flowjo = pd.DataFrame(
        [
            {
                "Sample_ID": "S1",
                "Population": "CD8+",
                "Count": "not a number",
                "Percent_of_Parent": "bad percent",
            }
        ]
    )

    results = convert_flowjo_to_sample_level_results(flowjo)

    assert pd.isna(results.loc[0, "Count"])
    assert pd.isna(results.loc[0, "Percent_of_Parent"])


def test_convert_flowjo_to_sample_level_results_skips_rows_without_sample_or_population():
    flowjo = pd.DataFrame(
        [
            {"Sample_ID": "", "Population": "CD8+", "Count": 1, "Percent_of_Parent": 1},
            {"Sample_ID": "S1", "Population": "", "Count": 1, "Percent_of_Parent": 1},
        ]
    )

    results = convert_flowjo_to_sample_level_results(flowjo)

    assert results.empty
    assert list(results.columns) == SAMPLE_LEVEL_RESULT_COLUMNS


def test_load_flowjo_results_reads_csv_export(tmp_path):
    csv_path = tmp_path / "flowjo.csv"
    pd.DataFrame(
        [
            {
                "Sample ID": "S1",
                "Gate Name": "CD8+",
                "Events": 100,
                "% Parent": 10,
            }
        ]
    ).to_csv(csv_path, index=False)

    results = load_flowjo_results(csv_path)

    assert results.loc[0, "Sample_ID"] == "S1"
    assert results.loc[0, "Exploratory_Path"] == "CD8+"


def test_load_flowjo_results_reads_tsv_export(tmp_path):
    tsv_path = tmp_path / "flowjo.tsv"
    pd.DataFrame(
        [{"Sample": "S1", "Population": "CD8+", "Count": 100, "Frequency": 10}]
    ).to_csv(tsv_path, sep="\t", index=False)

    results = load_flowjo_results(tsv_path)

    assert results.loc[0, "Sample_ID"] == "S1"


def test_load_flowjo_results_reads_excel_export(tmp_path):
    excel_path = tmp_path / "flowjo.xlsx"
    pd.DataFrame(
        [{"Sample": "S1", "Population": "CD8+", "Count": 100, "Frequency": 10}]
    ).to_excel(excel_path, index=False)

    results = load_flowjo_results(excel_path)

    assert results.loc[0, "Sample_ID"] == "S1"


def test_load_flowjo_results_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="FlowJo export file was not found"):
        load_flowjo_results(tmp_path / "missing.csv")


def test_load_flowjo_results_raises_for_unsupported_extension(tmp_path):
    path = tmp_path / "flowjo.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="FlowJo export must be"):
        load_flowjo_results(path)
