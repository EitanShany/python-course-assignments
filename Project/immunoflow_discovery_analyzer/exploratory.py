from itertools import combinations, product

import pandas as pd


def get_exploratory_starting_points(exploratory_search_df: pd.DataFrame) -> list[str]:
    """Return Starting_Population values from the Exploratory_Search sheet."""
    if "Starting_Population" not in exploratory_search_df.columns:
        return []
    return _get_unique_values(exploratory_search_df["Starting_Population"])


def get_markers_for_starting_population(
    marker_gates_df: pd.DataFrame,
    starting_population: str,
) -> list[str]:
    """Return markers whose Parent_Population matches the starting population."""
    required_columns = {"Marker", "Parent_Population"}
    if not required_columns.issubset(marker_gates_df.columns):
        return []

    normalized_starting_population = str(starting_population).strip().casefold()
    matching_rows = marker_gates_df[
        marker_gates_df["Parent_Population"].astype(str).str.strip().str.casefold()
        == normalized_starting_population
    ]
    return _get_unique_values(matching_rows["Marker"])


def generate_downstream_paths(
    starting_population: str,
    markers: list[str],
    max_depth: int | None = None,
) -> list[str]:
    """Generate marker-defined exploratory paths without using FCS data."""
    clean_markers = _get_unique_values(pd.Series(markers))
    if not clean_markers:
        return []

    if max_depth is None:
        depth_limit = len(clean_markers)
    else:
        depth_limit = min(max_depth, len(clean_markers))

    if depth_limit <= 0:
        return []

    paths: list[str] = []
    for path_length in range(1, depth_limit + 1):
        for marker_subset in combinations(clean_markers, path_length):
            for signs in product(["+", "-"], repeat=path_length):
                labels = [f"{marker}{sign}" for marker, sign in zip(marker_subset, signs)]
                paths.append(" -> ".join([str(starting_population).strip(), *labels]))

    return paths


def create_mock_exploratory_report(
    exploratory_search_df: pd.DataFrame,
    marker_gates_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create a mock exploratory report with candidate marker paths only."""
    rows: list[dict[str, str]] = []
    if "Starting_Population" not in exploratory_search_df.columns:
        return _empty_exploratory_report()

    for row_index, row in exploratory_search_df.iterrows():
        starting_population = str(row["Starting_Population"]).strip()
        if not starting_population:
            continue

        search_id = str(row.get("Search_ID", f"Search_{row_index + 1}")).strip()
        markers = get_markers_for_starting_population(marker_gates_df, starting_population)
        if not markers:
            markers = _get_unique_markers(marker_gates_df)

        for path in generate_downstream_paths(starting_population, markers):
            rows.append(
                {
                    "Search_ID": search_id,
                    "Starting_Population": starting_population,
                    "Exploratory_Path": path,
                    "Result_Type": "Exploratory",
                }
            )

    return pd.DataFrame(
        rows,
        columns=["Search_ID", "Starting_Population", "Exploratory_Path", "Result_Type"],
    )


def generate_exploratory_paths(
    marker_gates: pd.DataFrame,
    starting_population: str,
) -> list[dict[str, str]]:
    """Generate downstream marker paths from a Starting_Population."""
    markers = get_markers_for_starting_population(marker_gates, starting_population)
    if not markers:
        markers = _get_unique_markers(marker_gates)
    paths: list[dict[str, str]] = []

    for path_length in range(1, len(markers) + 1):
        for marker_subset in combinations(markers, path_length):
            for signs in product(["+", "-"], repeat=path_length):
                labels = [f"{marker}{sign}" for marker, sign in zip(marker_subset, signs)]
                paths.append(
                    {
                        "Starting_Population": starting_population,
                        "Path": " -> ".join([starting_population, *labels]),
                        "Phase": "Exploratory",
                    }
                )

    return paths


def generate_paths_from_workbook(workbook: dict[str, pd.DataFrame]) -> list[dict[str, str]]:
    marker_gates = workbook.get("Marker_Gates", pd.DataFrame())
    exploratory_search = workbook.get("Exploratory_Search", pd.DataFrame())

    all_paths = []
    for starting_population in get_exploratory_starting_points(exploratory_search):
        all_paths.extend(generate_exploratory_paths(marker_gates, starting_population))
    return all_paths


def _get_unique_markers(marker_gates: pd.DataFrame) -> list[str]:
    if "Marker" not in marker_gates.columns:
        return []
    return _get_unique_values(marker_gates["Marker"])


def _empty_exploratory_report() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["Search_ID", "Starting_Population", "Exploratory_Path", "Result_Type"]
    )


def _get_unique_values(values: pd.Series) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()

    for value in values.dropna():
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            unique_values.append(text)
            seen.add(key)

    return unique_values
