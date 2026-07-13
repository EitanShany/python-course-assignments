import pandas as pd

from immunoflow_discovery_analyzer.exploratory import (
    create_mock_exploratory_report,
    generate_downstream_paths,
    generate_exploratory_paths,
    generate_paths_from_workbook,
    get_exploratory_starting_points,
    get_markers_for_starting_population,
)


def test_generate_exploratory_paths_from_three_markers():
    marker_gates = pd.DataFrame(
        [
            {"Marker": "CD44"},
            {"Marker": "PD-1"},
            {"Marker": "TIM-3"},
        ]
    )

    paths = generate_exploratory_paths(marker_gates, "CD8+")
    path_texts = {path["Path"] for path in paths}

    assert len(paths) == 26
    assert "CD8+ -> CD44+" in path_texts
    assert "CD8+ -> CD44-" in path_texts
    assert "CD8+ -> PD-1+ -> TIM-3+" in path_texts
    assert "CD8+ -> CD44+ -> PD-1+ -> TIM-3+" in path_texts
    assert "CD8+ -> CD44- -> PD-1+ -> TIM-3-" in path_texts
    assert all(path["Phase"] == "Exploratory" for path in paths)


def test_generate_downstream_paths_from_starting_population_and_markers():
    paths = generate_downstream_paths("CD8+", ["CD44", "PD-1", "TIM-3"])

    assert len(paths) == 26
    assert "CD8+ -> CD44+" in paths
    assert "CD8+ -> CD44-" in paths
    assert "CD8+ -> PD-1+" in paths
    assert "CD8+ -> PD-1-" in paths
    assert "CD8+ -> CD44+ -> PD-1+" in paths
    assert "CD8+ -> CD44+ -> PD-1-" in paths
    assert "CD8+ -> CD44- -> PD-1+" in paths
    assert "CD8+ -> CD44- -> PD-1-" in paths
    assert "CD8+ -> CD44+ -> PD-1+ -> TIM-3+" in paths
    assert "CD8+ -> CD44+ -> PD-1+ -> TIM-3-" in paths


def test_generate_downstream_paths_respects_max_depth():
    paths = generate_downstream_paths("CD8+", ["CD44", "PD-1", "TIM-3"], max_depth=2)

    assert len(paths) == 18
    assert "CD8+ -> CD44+ -> PD-1+" in paths
    assert "CD8+ -> CD44+ -> TIM-3+" in paths
    assert all(path.count("->") <= 2 for path in paths)


def test_generate_downstream_paths_ignores_empty_and_duplicate_markers():
    paths = generate_downstream_paths("CD8+", ["CD44", " CD44 ", "", "PD-1"])

    assert len(paths) == 8
    assert paths[0] == "CD8+ -> CD44+"


def test_generate_downstream_paths_returns_empty_list_for_no_markers_or_zero_depth():
    assert generate_downstream_paths("CD8+", []) == []
    assert generate_downstream_paths("CD8+", ["CD44"], max_depth=0) == []


def test_generate_downstream_paths_for_two_markers_includes_expected_paths_without_duplicates():
    paths = generate_downstream_paths("CD8+", ["CD44", "PD1"])
    expected_paths = {
        "CD8+ -> CD44+",
        "CD8+ -> CD44-",
        "CD8+ -> PD1+",
        "CD8+ -> PD1-",
        "CD8+ -> CD44+ -> PD1+",
        "CD8+ -> CD44+ -> PD1-",
        "CD8+ -> CD44- -> PD1+",
        "CD8+ -> CD44- -> PD1-",
    }

    assert set(paths) == expected_paths
    assert len(paths) == len(set(paths))


def test_generate_paths_for_multiple_starting_populations():
    workbook = {
        "Marker_Gates": pd.DataFrame([{"Marker": "CD44"}, {"Marker": "PD-1"}]),
        "Exploratory_Search": pd.DataFrame(
            [{"Starting_Population": "CD8+"}, {"Starting_Population": "CD4+"}]
        ),
    }

    paths = generate_paths_from_workbook(workbook)

    assert len(paths) == 16
    assert {path["Starting_Population"] for path in paths} == {"CD8+", "CD4+"}


def test_get_exploratory_starting_points_returns_unique_non_empty_values():
    exploratory_search = pd.DataFrame(
        [
            {"Starting_Population": "CD8+"},
            {"Starting_Population": "CD4+"},
            {"Starting_Population": " CD8+ "},
            {"Starting_Population": ""},
            {"Starting_Population": None},
        ]
    )

    starting_points = get_exploratory_starting_points(exploratory_search)

    assert starting_points == ["CD8+", "CD4+"]


def test_get_exploratory_starting_points_returns_empty_list_when_column_missing():
    exploratory_search = pd.DataFrame([{"Search_ID": "S1"}])

    starting_points = get_exploratory_starting_points(exploratory_search)

    assert starting_points == []


def test_get_markers_for_starting_population_filters_by_parent_population():
    marker_gates = pd.DataFrame(
        [
            {"Marker": "CD44", "Parent_Population": "CD8+"},
            {"Marker": "PD-1", "Parent_Population": "CD8+"},
            {"Marker": "TIM-3", "Parent_Population": " CD8+ "},
            {"Marker": "FOXP3", "Parent_Population": "CD4+"},
        ]
    )

    markers = get_markers_for_starting_population(marker_gates, "CD8+")

    assert markers == ["CD44", "PD-1", "TIM-3"]


def test_get_markers_for_starting_population_returns_empty_list_when_columns_missing():
    marker_gates = pd.DataFrame([{"Marker": "CD44"}])

    markers = get_markers_for_starting_population(marker_gates, "CD8+")

    assert markers == []


def test_generate_exploratory_paths_uses_markers_for_requested_parent_population():
    marker_gates = pd.DataFrame(
        [
            {"Marker": "CD44", "Parent_Population": "CD8+"},
            {"Marker": "PD-1", "Parent_Population": "CD8+"},
            {"Marker": "FOXP3", "Parent_Population": "CD4+"},
        ]
    )

    paths = generate_exploratory_paths(marker_gates, "CD8+")
    path_texts = {path["Path"] for path in paths}

    assert len(paths) == 8
    assert "CD8+ -> CD44+" in path_texts
    assert "CD8+ -> PD-1-" in path_texts
    assert all("FOXP3" not in path["Path"] for path in paths)


def test_create_mock_exploratory_report_generates_candidate_paths_for_each_search():
    exploratory_search = pd.DataFrame(
        [
            {"Search_ID": "Search_CD8", "Starting_Population": "CD8+"},
            {"Search_ID": "Search_CD4", "Starting_Population": "CD4+"},
        ]
    )
    marker_gates = pd.DataFrame(
        [
            {"Marker": "CD44", "Parent_Population": "CD8+"},
            {"Marker": "PD1", "Parent_Population": "CD8+"},
            {"Marker": "FOXP3", "Parent_Population": "CD4+"},
        ]
    )

    report = create_mock_exploratory_report(exploratory_search, marker_gates)

    assert list(report.columns) == [
        "Search_ID",
        "Starting_Population",
        "Exploratory_Path",
        "Result_Type",
    ]
    assert set(report["Result_Type"]) == {"Exploratory"}
    assert "CD8+ -> CD44+ -> PD1+" in report["Exploratory_Path"].tolist()
    assert "CD4+ -> FOXP3+" in report["Exploratory_Path"].tolist()
    assert all("FOXP3" not in path for path in report[report["Search_ID"] == "Search_CD8"]["Exploratory_Path"])


def test_create_mock_exploratory_report_skips_empty_starting_population_and_uses_marker_fallback():
    exploratory_search = pd.DataFrame(
        [
            {"Search_ID": "Blank", "Starting_Population": ""},
            {"Search_ID": "Fallback", "Starting_Population": "CD8+"},
        ]
    )
    marker_gates = pd.DataFrame([{"Marker": "CD44"}])

    report = create_mock_exploratory_report(exploratory_search, marker_gates)

    assert set(report["Search_ID"]) == {"Fallback"}
    assert report["Exploratory_Path"].tolist() == ["CD8+ -> CD44+", "CD8+ -> CD44-"]


def test_create_mock_exploratory_report_returns_empty_report_without_starting_population_column():
    exploratory_search = pd.DataFrame([{"Search_ID": "Search_1"}])
    marker_gates = pd.DataFrame([{"Marker": "CD44", "Parent_Population": "CD8+"}])

    report = create_mock_exploratory_report(exploratory_search, marker_gates)

    assert report.empty
    assert list(report.columns) == [
        "Search_ID",
        "Starting_Population",
        "Exploratory_Path",
        "Result_Type",
    ]


def test_generate_exploratory_paths_returns_empty_list_when_no_marker_column_exists():
    marker_gates = pd.DataFrame([{"Parent_Population": "CD8+"}])

    paths = generate_exploratory_paths(marker_gates, "CD8+")

    assert paths == []
