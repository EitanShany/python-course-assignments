"""Shared matching helpers for source adapters."""

from __future__ import annotations

from antibody_processing import first_value, normalize_target_text


def row_matches_any_alias(
    row: dict[str, str],
    aliases: list[str],
    field_names: list[str] | None,
) -> bool:
    """Return True when any normalized alias appears in the selected row fields."""
    normalized_aliases = [
        normalize_target_text(alias)
        for alias in aliases
        if normalize_target_text(alias)
    ]
    if not normalized_aliases:
        return False

    if field_names is None:
        values = [str(value) for value in row.values()]
    else:
        values = [first_value(row, field_name) for field_name in field_names]
    normalized_text = normalize_target_text(" ".join(values))
    return any(alias in normalized_text for alias in normalized_aliases)


def matched_aliases_for_row(row: dict[str, str], aliases: list[str]) -> list[str]:
    """Return the aliases that actually matched a source row."""
    normalized_text = normalize_target_text(" ".join(str(value) for value in row.values()))
    matches = []
    for alias in aliases:
        normalized_alias = normalize_target_text(alias)
        if normalized_alias and normalized_alias in normalized_text and alias not in matches:
            matches.append(alias)
    return matches
