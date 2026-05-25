"""IEDB search adapter."""

from __future__ import annotations

from antibody_processing import (
    MISSING_VALUE,
    first_value,
    output_value,
    target_category,
)
from data_sources import (
    iedb_sequence_url,
    list_values,
    search_iedb_antigen_records,
    search_iedb_epitope_records,
)


def search_iedb(target_aliases: list[str], limit: int) -> list[dict[str, str | int]]:
    """Search IEDB antigen and epitope records for the target aliases."""
    records = [
        *search_iedb_antigen_records(target_aliases),
        *search_iedb_epitope_records(target_aliases),
    ]
    return [iedb_record_to_output_row(record) for record in records[: max(limit, 0)]]


def iedb_record_to_output_row(record: dict) -> dict[str, str | int]:
    """Convert one IEDB antigen/epitope record to the shared output schema."""
    target = first_iedb_antigen_name(record)
    references = record.get("reference_ids") or []
    pubmed_count = len(references) if isinstance(references, list) else 0

    return {
        "antibody_name": MISSING_VALUE,
        "target_antigen_or_gene": output_value(target),
        "target_category": output_value(target_category(target)),
        "cancer_indication": MISSING_VALUE,
        "antibody_species_or_type": MISSING_VALUE,
        "antibody_format": output_value(first_value(record, "structure_type")),
        "highest_clinical_trial": MISSING_VALUE,
        "estimated_status": MISSING_VALUE,
        "pubmed_reference_count": pubmed_count,
        "data_source": "IEDB",
        "sequence_page_url": output_value(iedb_sequence_url(record)),
        "heavy_variable_region_sequence": MISSING_VALUE,
        "light_variable_region_sequence": MISSING_VALUE,
    }


def first_iedb_antigen_name(record: dict) -> str:
    """Return the first useful antigen name from an IEDB record."""
    names = list_values(record.get("parent_source_antigen_names"))
    if names:
        return names[0]

    curated_antigens = record.get("curated_source_antigens") or []
    if isinstance(curated_antigens, list):
        for antigen in curated_antigens:
            if isinstance(antigen, dict):
                name = str(antigen.get("name", "")).strip()
                if name:
                    return name
    return ""
