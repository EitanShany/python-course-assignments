"""Processing functions for therapeutic antibody search results."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from openpyxl import Workbook


UNKNOWN_VALUES = {"", "na", "n/a", "none", "tbc", "nfd", "not available"}

OUTPUT_COLUMNS = [
    "antibody_name",
    "target_antigen_or_gene",
    "target_category",
    "cancer_indication",
    "antibody_species_or_type",
    "antibody_format",
    "highest_clinical_trial",
    "estimated_status",
    "pubmed_reference_count",
    "heavy_variable_region_sequence",
    "light_variable_region_sequence",
]

SPECIES_OPTIONS = ["Human", "Humanized", "Mouse / murine", "Chimeric", "Unknown", "Other"]

TARGET_ALIASES = {
    "4-1BB": ["4-1BB", "41BB", "TNFRSF9", "CD137"],
    "41BB": ["4-1BB", "41BB", "TNFRSF9", "CD137"],
    "CD137": ["4-1BB", "41BB", "TNFRSF9", "CD137"],
    "EPCAM": ["EPCAM", "HEPCAM", "CD326"],
    "HEPCAM": ["EPCAM", "HEPCAM", "CD326"],
    "CD326": ["EPCAM", "HEPCAM", "CD326"],
    "5T4": ["5T4", "TPBG", "WAIF1"],
    "TPBG": ["5T4", "TPBG", "WAIF1"],
    "PD-1": ["PD1", "PD-1", "PDCD1", "CD279"],
    "PD1": ["PD1", "PD-1", "PDCD1", "CD279"],
    "PD-L1": ["PDL1", "PD-L1", "CD274", "B7H1"],
    "PDL1": ["PDL1", "PD-L1", "CD274", "B7H1"],
}

CANCER_TARGET_CATEGORIES = {
    "PD1": "Immune checkpoint",
    "PDCD1": "Immune checkpoint",
    "PDL1": "Immune checkpoint",
    "CD274": "Immune checkpoint",
    "CTLA4": "Immune checkpoint",
    "EGFR": "Tumor-associated antigen",
    "ERBB2": "Tumor-associated antigen",
    "HER2": "Tumor-associated antigen",
    "EPCAM": "Tumor-associated antigen",
    "CD326": "Tumor-associated antigen",
    "TPBG": "Tumor-associated antigen",
    "5T4": "Tumor-associated antigen",
    "WAIF1": "Tumor-associated antigen",
    "MUC16": "Tumor-associated antigen",
    "CA125": "Tumor-associated antigen",
    "MSLN": "Tumor-associated antigen",
    "TROP2": "Tumor-associated antigen",
    "TACSTD2": "Tumor-associated antigen",
    "NECTIN4": "Tumor-associated antigen",
    "DLL3": "Tumor-associated antigen",
    "CD276": "Tumor-associated antigen / immune modulator",
    "B7H3": "Tumor-associated antigen / immune modulator",
    "CD3": "T-cell engager component",
    "CD8": "T-cell marker",
    "HLA": "Peptide-HLA / TCR-like target",
}


def clean_text(value: str | None) -> str:
    """Return a readable value instead of database placeholders."""
    if value is None:
        return ""

    value = value.strip()
    if value.lower() in UNKNOWN_VALUES:
        return ""
    return value


def first_value(row: dict[str, str], *field_names: str) -> str:
    """Return the first non-empty value from possible raw/processed columns."""
    for field_name in field_names:
        value = clean_text(row.get(field_name))
        if value:
            return value
    return ""


def normalize_target_text(value: str) -> str:
    """Normalize target text so aliases with punctuation still match."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


BUILT_IN_SPECIES_FILTERS = {
    normalize_target_text(species)
    for species in SPECIES_OPTIONS
    if species != "Other"
}


def expanded_target_queries(target_query: str, extra_aliases: list[str] | None = None) -> list[str]:
    """Return the user query plus known aliases for common cancer targets."""
    query = clean_text(target_query).upper()
    aliases = TARGET_ALIASES.get(query, [target_query])
    if extra_aliases:
        aliases = aliases + extra_aliases
    return list(dict.fromkeys(aliases))


def row_matches_target(
    row: dict[str, str],
    target_query: str,
    extra_aliases: list[str] | None = None,
) -> bool:
    """Check whether a Thera-SAbDab row matches the requested target/gene."""
    target = first_value(row, "Target", "target_antigen_or_gene")
    if not target or not clean_text(target_query):
        return False

    normalized_target = normalize_target_text(target)
    for query in expanded_target_queries(target_query, extra_aliases):
        if normalize_target_text(query) in normalized_target:
            return True
    return False


def antibody_species_or_type(genetics: str) -> str:
    """Convert Thera-SAbDab genetics/origin text into a simple label."""
    genetics = clean_text(genetics)
    lower_genetics = genetics.lower()

    if "murine" in lower_genetics:
        return "Mouse / murine"
    if "humanised" in lower_genetics or "humanized" in lower_genetics:
        return "Humanized"
    if "human" in lower_genetics:
        return "Human"
    if "chimeric" in lower_genetics:
        return "Chimeric"
    return genetics or "Unknown"


def target_category(target: str) -> str:
    """Classify a cancer target using a small practical lookup table."""
    upper_target = target.upper()
    for marker, category in CANCER_TARGET_CATEGORIES.items():
        if marker in upper_target:
            return category
    return "Other / unclassified"


def cancer_indication(row: dict[str, str]) -> str:
    """Combine approved, active, and discontinued cancer indications."""
    processed_indication = clean_text(row.get("cancer_indication"))
    if processed_indication:
        return processed_indication

    indication_fields = [
        "Conditions Approved",
        "Conditions Active",
        "Conditions Discontinued",
    ]
    values = []
    for field in indication_fields:
        value = clean_text(row.get(field))
        if value:
            values.append(value)
    return "; ".join(values) or "Unknown"


def build_processed_row(row: dict[str, str], pubmed_count: int) -> dict[str, str | int]:
    """Convert a raw database row into the final assignment output columns."""
    target = first_value(row, "Target", "target_antigen_or_gene")
    species_or_type = first_value(row, "antibody_species_or_type") or antibody_species_or_type(
        row.get("Genetics (Bispecifics delimited with semicolon)", "")
    )

    return {
        "antibody_name": first_value(row, "Therapeutic", "antibody_name"),
        "target_antigen_or_gene": target,
        "target_category": first_value(row, "target_category") or target_category(target),
        "cancer_indication": cancer_indication(row),
        "antibody_species_or_type": species_or_type,
        "antibody_format": first_value(row, "Format", "antibody_format") or "Unknown",
        "highest_clinical_trial": first_value(row, "Highest_Clin_Trial (Feb '25)", "highest_clinical_trial")
        or "Unknown",
        "estimated_status": first_value(row, "Est. Status", "estimated_status") or "Unknown",
        "pubmed_reference_count": pubmed_count,
        "heavy_variable_region_sequence": first_value(
            row, "HeavySequence", "heavy_variable_region_sequence"
        )
        or "Not available",
        "light_variable_region_sequence": first_value(
            row, "LightSequence", "light_variable_region_sequence"
        )
        or "Not available",
    }


def row_matches_species(row: dict[str, str], species_filters: list[str] | None = None) -> bool:
    """Check whether an antibody row matches the selected species/type filters."""
    if not species_filters:
        return True

    species = first_value(row, "antibody_species_or_type") or antibody_species_or_type(
        row.get("Genetics (Bispecifics delimited with semicolon)", "")
    )
    normalized_species = normalize_target_text(species)

    for species_filter in species_filters:
        normalized_filter = normalize_target_text(species_filter)
        if normalized_filter in BUILT_IN_SPECIES_FILTERS:
            if normalized_filter == normalized_species:
                return True
        elif normalized_filter in normalized_species:
            return True
    return False


def sort_by_quality(rows: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    """Sort rows by literature support, highest PubMed reference count first."""
    return sorted(rows, key=lambda row: int(row.get("pubmed_reference_count", 0)), reverse=True)


def filter_and_process_antibodies(
    raw_rows: list[dict[str, str]],
    target_query: str,
    limit: int,
    reference_counter,
    extra_aliases: list[str] | None = None,
    species_filters: list[str] | None = None,
) -> list[dict[str, str | int]]:
    """Filter antibodies by target and add PubMed reference counts."""
    matches = [
        row
        for row in raw_rows
        if row_matches_target(row, target_query, extra_aliases)
        and row_matches_species(row, species_filters)
    ]

    processed_rows = []
    for row in matches:
        antibody_name = first_value(row, "Therapeutic", "antibody_name")
        stored_count = first_value(row, "pubmed_reference_count")
        pubmed_count = int(stored_count) if stored_count.isdigit() else 0
        if antibody_name and not stored_count:
            pubmed_count = reference_counter(antibody_name)
        processed_rows.append(build_processed_row(row, pubmed_count))

    return sort_by_quality(processed_rows)[: max(limit, 0)]


def write_results(output_path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write processed antibody rows to a CSV file."""
    with output_path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_excel_results(output_path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write processed antibody rows to an Excel workbook."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "antibody_results"
    worksheet.append(OUTPUT_COLUMNS)

    for row in rows:
        worksheet.append([row.get(column, "") for column in OUTPUT_COLUMNS])

    workbook.save(output_path)
