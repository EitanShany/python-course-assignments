"""Pytest tests for the Day06 antibody processing module."""

from pathlib import Path

from antibody_processing import (
    MISSING_VALUE,
    OUTPUT_COLUMNS,
    antibody_species_or_type,
    build_processed_row,
    deduplicate_results,
    expanded_target_queries,
    filter_and_process_antibodies,
    row_matches_target,
    row_matches_species,
    target_category,
    write_excel_results,
    write_results,
)
import data_sources
from data_sources import (
    document_matches_seed_aliases,
    extract_iedb_antigen_aliases,
    fetch_ncbi_gene_aliases,
    format_iedb_array_value,
    iedb_record_matches_seed_aliases,
    load_antibody_table,
)
from multi_source_search import search_all_sources
from sources.iedb_source import iedb_record_to_output_row
from sources.lens_patseq_source import lens_patseq_row_to_output_row
from sources.plabdab_source import plabdab_row_to_output_row


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


def test_expanded_target_queries_handles_clec9a_aliases_and_typo() -> None:
    aliases = expanded_target_queries("Cleac9a")

    assert "CLEC9A" in aliases
    assert "DNGR1" in aliases
    assert "CD370" in aliases


def test_row_matches_target_uses_extra_aliases() -> None:
    row = {**sample_row(), "Target": "TPBG/WAIF1"}

    assert row_matches_target(row, "unknown name", extra_aliases=["5T4", "TPBG"])


def test_antibody_species_or_type() -> None:
    assert antibody_species_or_type("Murine") == "Mouse / murine"
    assert antibody_species_or_type("Humanised") == "Humanized"
    assert antibody_species_or_type("Human") == "Human"
    assert antibody_species_or_type("") == ""


def test_row_matches_species_filter() -> None:
    human_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Humanised"}
    mouse_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Murine"}
    fully_human_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Human"}

    assert row_matches_species(human_row, ["Humanized"])
    assert not row_matches_species(human_row, ["Human"])
    assert row_matches_species(fully_human_row, ["Human"])
    assert row_matches_species(mouse_row, ["Mouse / murine"])
    assert not row_matches_species(mouse_row, ["Human"])


def test_unknown_species_filter_matches_missing_species() -> None:
    unknown_row = {**sample_row(), "Genetics (Bispecifics delimited with semicolon)": "Unknown"}

    assert row_matches_species(unknown_row, ["Unknown"])


def test_target_category_for_checkpoint() -> None:
    assert target_category("PDCD1/CD279/PD1") == "Immune checkpoint"
    assert target_category("PD-1") == "Immune checkpoint"
    assert target_category("B7-H3") == "Tumor-associated antigen / immune modulator"
    assert target_category("TPBG/WAIF1") == "Tumor-associated antigen"


def test_target_category_prefers_matched_alias_over_long_target_text() -> None:
    assert target_category("PD1; CLEC9A; CD370", preferred_markers=["CLEC9A"]) == "Dendritic-cell target"
    assert target_category("PD1; DNGR-1", preferred_markers=["DNGR-1"]) == "Dendritic-cell target"


def test_build_processed_row_has_engineering_columns() -> None:
    processed = build_processed_row(sample_row(), pubmed_count=12)

    assert processed["antibody_name"] == "Testimab"
    assert processed["target_category"] == "Immune checkpoint"
    assert processed["cancer_indication"] == "Melanoma; Lung cancer"
    assert processed["antibody_format"] == "Whole mAb"
    assert processed["pubmed_reference_count"] == 12
    assert processed["data_source"] == "Thera-SAbDab"
    assert processed["heavy_variable_region_sequence"] == "QVQLVESGGG"


def test_build_processed_row_fills_missing_values_with_na() -> None:
    processed = build_processed_row({"Therapeutic": "", "Target": ""}, pubmed_count=0)

    assert processed["antibody_name"] == MISSING_VALUE
    assert processed["cancer_indication"] == MISSING_VALUE
    assert processed["antibody_species_or_type"] == MISSING_VALUE
    assert processed["sequence_page_url"] == MISSING_VALUE
    assert processed["heavy_variable_region_sequence"] == MISSING_VALUE


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


def test_ncbi_gene_alias_fetch_keeps_seed_aliases_when_no_records(monkeypatch) -> None:
    monkeypatch.setattr(data_sources, "read_entrez_record", lambda *args, **kwargs: {"IdList": []})

    aliases = fetch_ncbi_gene_aliases("CLEC9A", seed_aliases=["CLEC9A", "DNGR1", "CD370"])

    assert aliases == ["CLEC9A", "DNGR1", "CD370"]


def test_iedb_alias_extraction_uses_antigen_names_and_curated_accessions() -> None:
    record = {
        "parent_source_antigen_id": "http://www.uniprot.org/uniprot/Q6UXN8",
        "parent_source_antigen_names": ["C-type lectin domain family 9 member A"],
        "curated_source_antigens": [
            {
                "accession": "Q6UXN8",
                "name": "C-type lectin domain family 9 member A",
            }
        ],
    }

    aliases = extract_iedb_antigen_aliases(record)

    assert "C-type lectin domain family 9 member A" in aliases
    assert "Q6UXN8" in aliases


def test_iedb_array_values_are_quoted_for_multiword_names() -> None:
    assert format_iedb_array_value("CLEC9A") == "CLEC9A"
    assert format_iedb_array_value('A "quoted" antigen') == '"A \\"quoted\\" antigen"'


def test_fetch_iedb_antigen_aliases_uses_injected_records(monkeypatch) -> None:
    def fake_fetch_iedb_antigen_records(query: str, max_records: int = 10) -> list[dict]:
        return [
            {
                "parent_source_antigen_names": [f"{query} antigen"],
                "curated_source_antigens": [{"name": "DNGR-1", "accession": "Q6UXN8"}],
            }
        ]

    monkeypatch.setattr(data_sources, "fetch_iedb_antigen_records", fake_fetch_iedb_antigen_records)

    aliases = data_sources.fetch_iedb_antigen_aliases("CLEC9A", seed_aliases=["CLEC9A"])

    assert "CLEC9A antigen" in aliases
    assert "DNGR-1" in aliases


def test_fetch_iedb_antigen_aliases_scans_when_exact_match_fails(monkeypatch) -> None:
    monkeypatch.setattr(data_sources, "fetch_iedb_antigen_records", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        data_sources,
        "search_iedb_antigen_records",
        lambda seed_aliases: [
            {
                "parent_source_antigen_names": ["C-type lectin domain family 9 member A"],
                "curated_source_antigens": [{"name": "DNGR-1", "accession": "Q6UXN8"}],
            }
        ],
    )

    aliases = data_sources.fetch_iedb_antigen_aliases("CLEC9A", seed_aliases=["CLEC9A"])

    assert "C-type lectin domain family 9 member A" in aliases
    assert "Q6UXN8" in aliases


def test_iedb_record_matches_seed_aliases() -> None:
    record = {
        "parent_source_antigen_names": ["DNGR-1"],
        "curated_source_antigens": [{"name": "C-type lectin domain family 9 member A"}],
    }

    assert iedb_record_matches_seed_aliases(record, ["DNGR1"])


def test_iedb_record_to_output_row_has_source_and_epitope_url() -> None:
    record = {
        "structure_id": 12345,
        "structure_type": "Linear peptide",
        "reference_ids": [1, 2],
        "curated_source_antigens": [{"name": "CLEC9A"}],
    }

    row = iedb_record_to_output_row(record)

    assert row["data_source"] == "IEDB"
    assert row["sequence_page_url"] == "https://www.iedb.org/epitope/12345"
    assert row["pubmed_reference_count"] == 2


def test_plabdab_row_to_output_row_maps_sequences_and_source_url() -> None:
    row = plabdab_row_to_output_row(
        {
            "ID": "ABC123",
            "heavy_sequence": "QVQLV",
            "light_sequence": "EIVMT",
            "targets_mentioned": "CLEC9A",
            "organism": "Homo sapiens",
            "heavy_definition": "single chain antibody",
        },
        matched_aliases=["CLEC9A"],
    )

    assert row["data_source"] == "PLAbDab"
    assert row["antibody_name"] == "ABC123"
    assert row["target_antigen_or_gene"] == "CLEC9A"
    assert row["antibody_format"] == "scFv"
    assert row["sequence_page_url"] == "https://www.ncbi.nlm.nih.gov/protein/ABC123"


def test_lens_patseq_row_to_output_row_maps_sequence_export() -> None:
    row = lens_patseq_row_to_output_row(
        {
            "id": "LENSSEQ1",
            "description": "CLEC9A antibody patent sequence",
            "sequence": "EVQLV",
        }
    )

    assert row["data_source"] == "The Lens PatSeq"
    assert row["antibody_name"] == "LENSSEQ1"
    assert row["heavy_variable_region_sequence"] == "EVQLV"
    assert "LENSSEQ1" in row["sequence_page_url"]


def test_deduplicate_results_merges_source_and_link_columns() -> None:
    row = build_processed_row(sample_row(), pubmed_count=3)
    duplicate = {
        **row,
        "data_source": "PLAbDab",
        "sequence_page_url": "https://example.test/sequence",
        "pubmed_reference_count": 9,
    }

    deduplicated = deduplicate_results([row, duplicate])

    assert len(deduplicated) == 1
    assert deduplicated[0]["pubmed_reference_count"] == 9
    assert deduplicated[0]["data_source"] == "Thera-SAbDab; PLAbDab"
    assert deduplicated[0]["sequence_page_url"] == "https://example.test/sequence"


def test_deduplicate_results_keeps_unnamed_rows_with_different_links() -> None:
    first_row = {
        "target_antigen_or_gene": "CLEC9A",
        "sequence_page_url": "https://www.iedb.org/epitope/1",
        "data_source": "IEDB",
    }
    second_row = {
        "target_antigen_or_gene": "CLEC9A",
        "sequence_page_url": "https://www.iedb.org/epitope/2",
        "data_source": "IEDB",
    }

    assert len(deduplicate_results([first_row, second_row])) == 2


def test_search_all_sources_merges_parallel_adapters(monkeypatch) -> None:
    monkeypatch.setattr("multi_source_search.search_iedb", lambda aliases, limit: [])
    monkeypatch.setattr(
        "multi_source_search.search_plabdab",
        lambda aliases, limit: [
            {
                **build_processed_row(sample_row(), pubmed_count=0, data_source="PLAbDab"),
                "sequence_page_url": "https://example.test/plabdab",
            }
        ],
    )
    monkeypatch.setattr("multi_source_search.search_lens_patseq", lambda aliases, limit: [])

    rows = search_all_sources(
        therasabdab_loader=lambda: [sample_row()],
        target_query="PD1",
        target_aliases=["PD1"],
        limit=10,
        reference_counter=lambda antibody_name: 4,
    )

    assert len(rows) == 1
    assert set(str(rows[0]["data_source"]).split("; ")) == {"PLAbDab", "Thera-SAbDab"}
    assert rows[0]["sequence_page_url"] == "https://example.test/plabdab"


def test_output_columns_include_source_metadata() -> None:
    assert "data_source" in OUTPUT_COLUMNS
    assert "sequence_page_url" in OUTPUT_COLUMNS



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
