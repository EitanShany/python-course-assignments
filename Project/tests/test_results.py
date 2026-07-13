import pandas as pd

from immunoflow_discovery_analyzer.results import (
    SAMPLE_LEVEL_RESULT_COLUMNS,
    create_mock_sample_level_results,
)


def test_create_mock_sample_level_results_crosses_samples_with_paths():
    plate_map = pd.DataFrame(
        [
            {"Sample_ID": "S1", "FCS_File": "sample1.fcs"},
            {"Sample_ID": "S2", "FCS_File": "sample2.fcs"},
        ]
    )
    exploratory_paths = pd.DataFrame(
        [
            {
                "Search_ID": "Search_1",
                "Starting_Population": "CD8+",
                "Exploratory_Path": "CD8+ -> CD44+",
                "Result_Type": "Exploratory",
            },
            {
                "Search_ID": "Search_1",
                "Starting_Population": "CD8+",
                "Exploratory_Path": "CD8+ -> CD44-",
                "Result_Type": "Exploratory",
            },
        ]
    )

    results = create_mock_sample_level_results(plate_map, exploratory_paths)

    assert list(results.columns) == SAMPLE_LEVEL_RESULT_COLUMNS
    assert len(results) == 4
    assert set(results["Sample_ID"]) == {"S1", "S2"}
    assert set(results["Result_Type"]) == {"Exploratory"}
    assert results["Count"].notna().all()
    assert results["Percent_of_Parent"].notna().all()


def test_create_mock_sample_level_results_returns_empty_table_for_empty_inputs():
    results = create_mock_sample_level_results(pd.DataFrame(), pd.DataFrame())

    assert results.empty
    assert list(results.columns) == SAMPLE_LEVEL_RESULT_COLUMNS
