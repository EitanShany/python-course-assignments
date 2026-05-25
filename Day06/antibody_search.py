"""Command-line program that integrates the Day06 antibody modules."""

from __future__ import annotations

import argparse
import urllib.error
from pathlib import Path

from antibody_processing import (
    expanded_target_queries,
    write_excel_results,
    write_results,
)
from data_sources import (
    count_pubmed_references,
    fetch_iedb_antigen_aliases,
    fetch_ncbi_gene_aliases,
    load_antibody_table,
    write_target_aliases,
)
from multi_source_search import search_all_sources


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search Thera-SAbDab for antibodies against a cancer target."
    )
    parser.add_argument(
        "--target",
        help="Target antigen/gene to search for, for example PD1, EGFR, HER2, or MUC16.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of matching antibodies to process. Default: 20.",
    )
    parser.add_argument(
        "--output",
        default="antibody_results.csv",
        help="Output file name, CSV or XLSX. Default: antibody_results.csv.",
    )
    parser.add_argument(
        "--species",
        help="Optional comma-separated species/type filters, for example Human,Humanized.",
    )
    parser.add_argument(
        "--input-file",
        help="Optional local CSV/XLSX antibody table instead of downloading Thera-SAbDab.",
    )
    return parser.parse_args()


def safe_count_pubmed_references(antibody_name: str) -> int:
    """Return a PubMed count, or zero if PubMed is temporarily unavailable."""
    try:
        return count_pubmed_references(antibody_name)
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, RuntimeError) as error:
        print(f"Could not count PubMed references for {antibody_name}: {error}")
        return 0


def safe_fetch_gene_aliases(target_query: str) -> list[str]:
    """Return NCBI Gene and IEDB aliases, or just the query if sites are unavailable."""
    seed_aliases = expanded_target_queries(target_query)
    try:
        aliases = fetch_ncbi_gene_aliases(target_query, seed_aliases=seed_aliases)
    except Exception as error:
        print(f"Could not fetch NCBI Gene aliases for {target_query}: {error}")
        aliases = seed_aliases

    try:
        iedb_aliases = fetch_iedb_antigen_aliases(target_query, seed_aliases=aliases)
        aliases = list(dict.fromkeys([*aliases, *iedb_aliases]))
    except Exception as error:
        print(f"Could not fetch IEDB antigen aliases for {target_query}: {error}")

    alias_path = write_target_aliases(target_query, aliases)
    print(f"Target aliases saved to: {alias_path}")
    return aliases


def print_summary(target_query: str, rows: list[dict[str, str | int]], output_path: Path) -> None:
    """Print a short summary for the user."""
    print()
    print(f"Target searched: {target_query}")
    print(f"Antibodies found: {len(rows)}")

    if not rows:
        print("No matching antibodies were found. Try PD1, PDL1, EGFR, HER2, or MUC16.")
        return

    print(f"Results saved to: {output_path}")
    print()
    print("Top results:")
    for row in rows[:5]:
        safe_print(
            "- "
            f"{summary_value(row['antibody_name'])} | "
            f"target: {summary_value(row['target_antigen_or_gene'])} | "
            f"source: {summary_value(row.get('data_source', 'N.A'))} | "
            f"PubMed refs: {row['pubmed_reference_count']}"
        )


def parse_species_filters(species_text: str | None) -> list[str]:
    """Parse comma-separated species filters from the command line."""
    if not species_text:
        return []
    return [species.strip() for species in species_text.split(",") if species.strip()]


def summary_value(value: str | int, max_length: int = 120) -> str:
    """Return a compact one-line value for CLI summaries."""
    text = str(value).replace("\n", " ").strip()
    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def safe_print(text: str) -> None:
    """Print text safely on Windows consoles with narrow encodings."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def save_output(output_path: Path, rows: list[dict[str, str | int]]) -> None:
    """Save results as CSV or Excel according to the file extension."""
    if output_path.suffix.lower() in {".xlsx", ".xlsm"}:
        write_excel_results(output_path, rows)
    else:
        write_results(output_path, rows)


def main() -> None:
    args = parse_arguments()
    target_query = args.target or input("Enter cancer target/antigen/gene name: ").strip()

    if not target_query:
        print("No target was entered.")
        return

    print("Fetching target aliases from NCBI Gene and IEDB...")
    target_aliases = safe_fetch_gene_aliases(target_query)

    input_file = Path(args.input_file) if args.input_file else None
    if input_file:
        print(f"Searching sources using local Thera-SAbDab table from {input_file}...")
    else:
        print("Searching sources in parallel...")

    processed_rows = search_all_sources(
        therasabdab_loader=lambda: load_antibody_table(input_file),
        target_query=target_query,
        target_aliases=target_aliases,
        limit=args.limit,
        reference_counter=safe_count_pubmed_references,
        species_filters=parse_species_filters(args.species),
    )

    output_path = Path(args.output)
    save_output(output_path, processed_rows)
    print_summary(target_query, processed_rows, output_path)


if __name__ == "__main__":
    main()
