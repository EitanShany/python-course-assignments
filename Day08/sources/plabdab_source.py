"""PLAbDab search adapter."""

from __future__ import annotations

from antibody_processing import (
    MISSING_VALUE,
    first_value,
    output_value,
    target_category,
)
from data_sources import download_plabdab_paired_table
from sources.matching import matched_aliases_for_row, row_matches_any_alias


PLABDAB_SEARCH_FIELDS = [
    "targets_mentioned",
    "heavy_definition",
    "light_definition",
    "reference_title",
]


def search_plabdab(target_aliases: list[str], limit: int) -> list[dict[str, str | int]]:
    """Search PLAbDab paired sequences by target keywords."""
    rows = download_plabdab_paired_table()
    matches = [
        plabdab_row_to_output_row(row, matched_aliases=matched_aliases_for_row(row, target_aliases))
        for row in rows
        if row_matches_any_alias(row, target_aliases, PLABDAB_SEARCH_FIELDS)
    ]
    return matches[: max(limit, 0)]


def plabdab_row_to_output_row(
    row: dict[str, str],
    matched_aliases: list[str] | None = None,
) -> dict[str, str | int]:
    """Convert one PLAbDab row to the shared output schema."""
    target = "; ".join(matched_aliases or []) or first_value(row, "targets_mentioned")
    sequence_id = first_value(row, "ID", "heavy_ID", "light_ID")

    return {
        "antibody_name": output_value(first_value(row, "ID")),
        "target_antigen_or_gene": output_value(target),
        "target_category": output_value(target_category(target, preferred_markers=matched_aliases)),
        "cancer_indication": MISSING_VALUE,
        "antibody_species_or_type": output_value(first_value(row, "organism")),
        "antibody_format": output_value(infer_antibody_format(row)),
        "highest_clinical_trial": MISSING_VALUE,
        "estimated_status": MISSING_VALUE,
        "pubmed_reference_count": 0,
        "data_source": "PLAbDab",
        "sequence_page_url": output_value(sequence_url_from_accession(sequence_id)),
        "heavy_variable_region_sequence": output_value(first_value(row, "heavy_sequence")),
        "light_variable_region_sequence": output_value(first_value(row, "light_sequence")),
    }


def infer_antibody_format(row: dict[str, str]) -> str:
    """Infer a simple antibody format from PLAbDab free-text fields."""
    text = " ".join(
        [
            first_value(row, "heavy_definition"),
            first_value(row, "light_definition"),
            first_value(row, "reference_title"),
        ]
    ).lower()
    if "single chain" in text or "scfv" in text:
        return "scFv"
    if "fab" in text:
        return "Fab"
    if "nanobody" in text or "vhh" in text:
        return "VHH / nanobody"
    return ""


def sequence_url_from_accession(accession: str) -> str:
    """Return a public protein accession page for a PLAbDab sequence id."""
    if not accession:
        return ""
    return f"https://www.ncbi.nlm.nih.gov/protein/{accession}"
