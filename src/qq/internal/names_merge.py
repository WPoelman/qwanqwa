"""Merge name data collected from multiple importers."""

import dataclasses

from qq.data_model import NameEntry


def merge_name_data(all_name_data: list[dict[str, list[NameEntry]]]) -> dict[str, list[NameEntry]]:
    """Merge name data from multiple importers.

    For each languoid, collects all name entries from all sources and
    deduplicates by (bcp_47_code, name). When duplicates exist, prefers
    the entry with is_canonical=True.

    Args:
        all_name_data: List of dicts, each mapping canonical ID -> list of NameEntry objects.

    Returns:
        Merged dict mapping canonical ID -> deduplicated list of NameEntry objects.
    """
    merged: dict[str, list[NameEntry]] = {}

    for source_data in all_name_data:
        for canonical_id, entries in source_data.items():
            if canonical_id not in merged:
                merged[canonical_id] = []
            merged[canonical_id].extend(entries)

    # Deduplicate per languoid
    for canonical_id, entries in merged.items():
        merged[canonical_id] = _deduplicate_entries(entries)

    return merged


def resolve_locale_codes(name_data_dict: dict[str, list[NameEntry]], resolver) -> dict[str, list[NameEntry]]:
    """Resolve BCP-47 locale codes to canonical IDs in name data entries.

    Importers store name data with 'bcp_47_code' as the locale key. This
    function resolves those codes to canonical IDs and stores them in 'locale_id',
    so that the exported names.zip uses stable canonical IDs as lookup keys
    while the original BCP-47 code is preserved in 'bcp_47_code'.

    Entries where the BCP-47 code cannot be resolved get locale_id=None.

    Args:
        name_data_dict: Merged dict mapping languoid canonical ID -> list of NameEntry objects.
        resolver: EntityResolver used to resolve BCP-47 locale codes.

    Returns:
        New dict with entries where locale_id holds the resolved canonical ID.
    """
    from qq.data_model import IdType

    resolved: dict[str, list[NameEntry]] = {}
    for lang_id, entries in name_data_dict.items():
        resolved_entries: list[NameEntry] = []
        for entry in entries:
            bcp_47 = entry.bcp_47_code
            if bcp_47 is not None:
                locale_id = resolver.resolve(IdType.BCP_47, bcp_47)
                resolved_entries.append(dataclasses.replace(entry, locale_id=locale_id))
            else:
                resolved_entries.append(entry)
        resolved[lang_id] = resolved_entries
    return resolved


def _deduplicate_entries(entries: list[NameEntry]) -> list[NameEntry]:
    """Deduplicate name entries by (bcp_47_code, name), preferring is_canonical=True."""
    seen: dict[tuple[str | None, str], NameEntry] = {}

    for entry in entries:
        key = (entry.bcp_47_code, entry.name)
        existing = seen.get(key)
        if existing is None:
            seen[key] = entry
        elif entry.is_canonical and not existing.is_canonical:
            seen[key] = entry

    return list(seen.values())
