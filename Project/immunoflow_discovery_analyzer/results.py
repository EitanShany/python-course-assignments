import pandas as pd


SAMPLE_LEVEL_RESULT_COLUMNS = [
    "Sample_ID",
    "FCS_File",
    "Search_ID",
    "Starting_Population",
    "Exploratory_Path",
    "Count",
    "Percent_of_Parent",
    "Result_Type",
]


def create_mock_sample_level_results(
    plate_map_df: pd.DataFrame,
    exploratory_paths_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create temporary mock sample-level exploratory results."""
    if plate_map_df.empty or exploratory_paths_df.empty:
        return _empty_sample_level_results()

    rows: list[dict[str, object]] = []
    for sample_index, sample in plate_map_df.iterrows():
        sample_id = str(sample.get("Sample_ID", f"Sample_{sample_index + 1}")).strip()
        fcs_file = str(sample.get("FCS_File", "")).strip()

        for path_index, path_row in exploratory_paths_df.iterrows():
            exploratory_path = str(path_row["Exploratory_Path"]).strip()
            rows.append(
                {
                    "Sample_ID": sample_id,
                    "FCS_File": fcs_file,
                    "Search_ID": str(path_row.get("Search_ID", "")).strip(),
                    "Starting_Population": str(path_row.get("Starting_Population", "")).strip(),
                    "Exploratory_Path": exploratory_path,
                    "Count": _mock_count(sample_index, path_index, exploratory_path),
                    "Percent_of_Parent": _mock_percent(sample_index, path_index),
                    "Result_Type": "Exploratory",
                }
            )

    return pd.DataFrame(rows, columns=SAMPLE_LEVEL_RESULT_COLUMNS)


def _mock_count(sample_index: int, path_index: int, exploratory_path: str) -> int:
    return 1000 + sample_index * 100 + path_index * 10 + len(exploratory_path)


def _mock_percent(sample_index: int, path_index: int) -> float:
    return round(5.0 + sample_index * 0.5 + path_index * 0.1, 3)


def _empty_sample_level_results() -> pd.DataFrame:
    return pd.DataFrame(columns=SAMPLE_LEVEL_RESULT_COLUMNS)
