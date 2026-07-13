from immunoflow_discovery_analyzer.gating import GatingEngine


def test_gating_engine_initializes_in_mock_mode_by_default():
    engine = GatingEngine()

    assert engine.mode == "mock"


def test_run_closed_gating_returns_mock_population_counts():
    engine = GatingEngine()

    result = engine.run_closed_gating({"Sample_ID": "S1"})

    assert result["Sample_ID"] == "S1"
    assert result["Cells"] == 100000
    assert result["CD8+"] == 22000


def test_run_exploratory_path_returns_mock_count_and_percentage():
    engine = GatingEngine()

    result = engine.run_exploratory_path({"Sample_ID": "S1"}, "CD8+ -> CD44+")

    assert result["Sample_ID"] == "S1"
    assert result["Exploratory_Path"] == "CD8+ -> CD44+"
    assert result["Mock_Count"] > 0
    assert result["Mock_Percentage"] > 0


def test_gating_engine_reads_lowercase_sample_id_attribute():
    class Sample:
        sample_id = "S-lower"

    engine = GatingEngine()

    result = engine.run_closed_gating(Sample())

    assert result["Sample_ID"] == "S-lower"
