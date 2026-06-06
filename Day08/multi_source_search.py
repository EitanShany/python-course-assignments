"""Parallel orchestration for antibody and sequence source adapters."""

from __future__ import annotations

import concurrent.futures

from antibody_processing import deduplicate_results, sort_by_quality
from sources.iedb_source import search_iedb
from sources.lens_patseq_source import search_lens_patseq
from sources.plabdab_source import search_plabdab
from sources.therasabdab_source import ReferenceCounter, TheraSAbDabLoader, search_therasabdab


def search_all_sources(
    therasabdab_loader: TheraSAbDabLoader,
    target_query: str,
    target_aliases: list[str],
    limit: int,
    reference_counter: ReferenceCounter,
    species_filters: list[str] | None = None,
) -> list[dict[str, str | int]]:
    """Search all configured sources in parallel and return one merged table."""
    search_jobs = [
        (
            "Thera-SAbDab",
            lambda: search_therasabdab(
                therasabdab_loader,
                target_query,
                target_aliases,
                limit,
                reference_counter,
                species_filters,
            ),
        ),
        ("IEDB", lambda: search_iedb(target_aliases, limit)),
        ("PLAbDab", lambda: search_plabdab(target_aliases, limit)),
        ("The Lens PatSeq", lambda: search_lens_patseq(target_aliases, limit)),
    ]

    rows: list[dict[str, str | int]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(search_jobs)) as executor:
        future_to_source = {
            executor.submit(search_function): source_name
            for source_name, search_function in search_jobs
        }
        for future in concurrent.futures.as_completed(future_to_source):
            source_name = future_to_source[future]
            try:
                rows.extend(future.result())
            except Exception as error:
                print(f"Could not search {source_name}: {error}")

    return sort_by_quality(deduplicate_results(rows))[: max(limit, 0)]
