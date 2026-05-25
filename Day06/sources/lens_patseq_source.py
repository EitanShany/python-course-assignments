"""The Lens PatSeq search adapter."""

from __future__ import annotations

from antibody_processing import (
    MISSING_VALUE,
    first_value,
    output_value,
    target_category,
)
from data_sources import read_lens_patseq_file
from sources.matching import row_matches_any_alias


def search_lens_patseq(target_aliases: list[str], limit: int) -> list[dict[str, str | int]]:
    """Search a configured Lens PatSeq export file by target aliases."""
    rows = read_lens_patseq_file()
    matches = [
        lens_patseq_row_to_output_row(row)
        for row in rows
        if row_matches_any_alias(row, target_aliases, None)
    ]
    return matches[: max(limit, 0)]


def lens_patseq_row_to_output_row(row: dict[str, str]) -> dict[str, str | int]:
    """Convert one Lens PatSeq export row to the shared output schema."""
    sequence = first_value(
        row,
        "sequence",
        "Sequence",
        "amino_acid_sequence",
        "Amino Acid Sequence",
    )
    target = first_value(row, "target", "Target", "antigen", "Antigen", "description")
    record_id = first_value(row, "id", "ID", "patent_sequence_id", "sequence_id")

    return {
        "antibody_name": output_value(record_id),
        "target_antigen_or_gene": output_value(target),
        "target_category": output_value(target_category(target)),
        "cancer_indication": MISSING_VALUE,
        "antibody_species_or_type": MISSING_VALUE,
        "antibody_format": MISSING_VALUE,
        "highest_clinical_trial": MISSING_VALUE,
        "estimated_status": MISSING_VALUE,
        "pubmed_reference_count": 0,
        "data_source": "The Lens PatSeq",
        "sequence_page_url": output_value(lens_sequence_url(row, record_id)),
        "heavy_variable_region_sequence": output_value(sequence),
        "light_variable_region_sequence": MISSING_VALUE,
    }


def lens_sequence_url(row: dict[str, str], record_id: str) -> str:
    """Return the best available Lens sequence or patent URL from an export row."""
    for field_name in ("sequence_page_url", "url", "URL", "lens_url", "patent_url"):
        url = first_value(row, field_name)
        if url:
            return url
    if record_id:
        return f"https://www.lens.org/lens/search/patseq/list?q={record_id}"
    return ""
