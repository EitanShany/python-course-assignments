"""Thera-SAbDab search adapter."""

from __future__ import annotations

from collections.abc import Callable

from antibody_processing import filter_and_process_antibodies


ReferenceCounter = Callable[[str], int]
TheraSAbDabLoader = Callable[[], list[dict[str, str]]]


def search_therasabdab(
    therasabdab_loader: TheraSAbDabLoader,
    target_query: str,
    target_aliases: list[str],
    limit: int,
    reference_counter: ReferenceCounter,
    species_filters: list[str] | None = None,
) -> list[dict[str, str | int]]:
    """Load and search Thera-SAbDab rows with PubMed reference counting."""
    raw_rows = therasabdab_loader()
    return filter_and_process_antibodies(
        raw_rows=raw_rows,
        target_query=target_query,
        limit=limit,
        reference_counter=reference_counter,
        extra_aliases=target_aliases,
        species_filters=species_filters,
    )
