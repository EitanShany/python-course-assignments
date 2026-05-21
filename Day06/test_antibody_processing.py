"""Pytest tests for the Day06 antibody processing module."""

from pathlib import Path

from antibody_processing import (
    antibody_species_or_type,
    build_processed_row,
    filter_and_process_antibodies,
    row_matches_target,
    row_matches_species,
    target_category,
    write_excel_results,
    write_results,
)
from data_sources import document_matches_seed_aliases, load_antibody_table


def sample_row() -> dict[str, str]:
    return {
        "Therapeutic": "Testimab",
        "Target": "PDCD1/CD279/PD1",
        "Genetics (Bispecifics delimited with semicolon)": "Humanised",
        "Format": "Whole mAb",
        "Highest_Clin_Trial (Feb '25)": "Phase-II",
        "Est. Status": "Active",
        "Conditions Approved": "na",
        "Conditions Active": "Melanoma; Lung cancer",
        "Conditions Discontinued": "na",
        "HeavySequence": "QVQLVESGGG",
        "LightSequence": "EIVMTQSPAT",
    }


def test_row_matches_target_is_case_insensitive() -> None:
    assert row_matches_target(sample_row(), "pd1")
    assert row_matches_target(sample_row(), "PD-1")
    assert not row_matches_target(sample_row(), "egfr")


def test_row_matches_target_uses_common_cancer_aliases() -> None:
    epcam_row = {**sample_row(), "Target": "EPCAM/CD326"}
    five_t4_row = {**sample_row(), "Target": "TPBG/WAIF1"}

    assert row_matches_target(epcam_row, "hEpCAM")
    assert row_matches_target(five_t4_row, "5T4")


def test_row_matches_target_uses_extra_aliases() -> None:
    row = {**sample_row(), "Target": "TPBG/WAIF1"}

    assert row_matches_target(row, "unknown name", extra_aliases=["5T4", "TPBG"])


def test_antibody_species_or_type() -> None:
    assert antibody_species_or_type("Murine") == "Mouse / murine"
    assert antibody_species_or_type("Humanised") == "Humanized"
    assert antibody_species_or_type("Human") == "Human"


def test_row_matches_species_filter() -> None:
    human_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Humanised"}
    mouse_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Murine"}
    fully_human_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Human"}

    assert row_matches_species(human_row, ["Humanized"])
    assert not row_matches_species(human_row, ["Human"])
    assert row_matches_species(fully_human_row, ["Human"])
    assert row_matches_species(mouse_row, ["Mouse / murine"])
    assert not row_matches_species(mouse_row, ["Human"])


def test_target_category_for_checkpoint() -> None:
    assert target_category("PDCD1/CD279/PD1") == "Immune checkpoint"
    assert target_category("TPBG/WAIF1") == "Tumor-associated antigen"


def test_build_processed_row_has_engineering_columns() -> None:
    processed = build_processed_row(sample_row(), pubmed_count=12)

    assert processed["antibody_name"] == "Testimab"
    assert processed["target_category"] == "Immune checkpoint"
    assert processed["cancer_indication"] == "Melanoma; Lung cancer"
    assert processed["antibody_format"] == "Whole mAb"
    assert processed["pubmed_reference_count"] == 12
    assert processed["heavy_variable_region_sequence"] == "QVQLVESGGG"


def test_filter_and_process_uses_injected_reference_counter() -> None:
    rows = [sample_row(), {**sample_row(), "Therapeutic": "Otherimab", "Target": "EGFR"}]

    processed = filter_and_process_antibodies(
        raw_rows=rows,
        target_query="PD1",
        limit=10,
        reference_counter=lambda antibody_name: 7,
    )

    assert len(processed) == 1
    assert processed[0]["antibody_name"] == "Testimab"
    assert processed[0]["pubmed_reference_count"] == 7


def test_filter_and_process_filters_species_and_sorts_by_references() -> None:
    rows = [
        {**sample_row(), "Therapeutic": "LowRef", "Genetics (Bispecifics delimited with semicolon)": "Human"},
        {**sample_row(), "Therapeutic": "HighRef", "Genetics (Bispecifics delimited with semicolon)": "Human"},
        {**sample_row(), "Therapeutic": "MouseRef", "Genetics (Bispecifics delimited with semicolon)": "Murine"},
    ]
    counts = {"LowRef": 3, "HighRef": 20, "MouseRef": 100}

    processed = filter_and_process_antibodies(
        raw_rows=rows,
        target_query="PD1",
        limit=10,
        reference_counter=lambda antibody_name: counts[antibody_name],
        species_filters=["Human"],
    )

    assert [row["antibody_name"] for row in processed] == ["HighRef", "LowRef"]


def test_filter_and_process_uses_extra_aliases() -> None:
    rows = [{**sample_row(), "Therapeutic": "Naptumomab", "Target": "TPBG/WAIF1"}]

    processed = filter_and_process_antibodies(
        raw_rows=rows,
        target_query="5T4 antigen",
        limit=10,
        reference_counter=lambda antibody_name: 2,
        extra_aliases=["5T4", "TPBG"],
    )

    assert len(processed) == 1
    assert processed[0]["antibody_name"] == "Naptumomab"


def test_ncbi_gene_alias_filter_rejects_unrelated_records() -> None:
    unrelated_document = {
        "Name": "ACKR3",
        "Description": "atypical chemokine receptor 3",
        "OtherAliases": "CXCR7,RDC1",
        "OtherDesignations": "C-X-C chemokine receptor type 7",
    }
    related_document = {
        "Name": "TPBG",
        "Description": "trophoblast glycoprotein",
        "OtherAliases": "5T4AG,M6P1,WAIF1",
        "OtherDesignations": "5T4 oncofetal antigen",
    }

    assert not document_matches_seed_aliases(unrelated_document, ["5T4", "TPBG", "WAIF1"])
    assert document_matches_seed_aliases(related_document, ["5T4", "TPBG", "WAIF1"])


def test_write_results_creates_csv() -> None:
    output_path = Path("test_results.csv")
    rows = [build_processed_row(sample_row(), pubmed_count=3)]

    try:
        write_results(output_path, rows)

        with output_path.open(encoding="utf-8") as result_file:
            text = result_file.read()

        assert "antibody_name" in text
        assert "Testimab" in text
    finally:
        if output_path.exists():
            output_path.unlink()


def test_write_results_creates_header_for_empty_results() -> None:
    output_path = Path("empty_results.csv")

    try:
        write_results(output_path, [])

        with output_path.open(encoding="utf-8") as result_file:
            text = result_file.read()

        assert "antibody_name" in text
        assert "light_variable_region_sequence" in text
    finally:
        if output_path.exists():
            output_path.unlink()


def test_write_excel_results_and_loads_excel() -> None:
    output_path = Path("test_results.xlsx")
    rows = [build_processed_row(sample_row(), pubmed_count=5)]

    try:
        write_excel_results(output_path, rows)
        loaded_rows = load_antibody_table(output_path)

        assert loaded_rows[0]["antibody_name"] == "Testimab"
        assert loaded_rows[0]["pubmed_reference_count"] == "5"
    finally:
        if output_path.exists():
            output_path.unlink()


def test_load_csv_table() -> None:
    output_path = Path("test_results.csv")
    rows = [build_processed_row(sample_row(), pubmed_count=4)]

    try:
        write_results(output_path, rows)
        loaded_rows = load_antibody_table(output_path)

        assert loaded_rows[0]["antibody_name"] == "Testimab"
        assert loaded_rows[0]["pubmed_reference_count"] == "4"
    finally:
        if output_path.exists():
            output_path.unlink()
