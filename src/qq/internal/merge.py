"""
Merge step: combines per-source EntitySets into a final DataStore.

Pass 1 — Merge entity attributes:
  For each entity ID across all EntitySets, create one entity in the final
  DataStore. For each field in _data_fields, collect values from all sources.
  Single-source values pass through. Multi-source conflicts resolve by source
  priority (DataSource enum value — lower = higher priority). Lists are merged.

Pass 2 — Apply relations:
  Collect all relations from all EntitySets, apply to final store entities
  (only if both source and target exist).
"""

import json
import logging
from pathlib import Path
from typing import Any

from qq.data_model import TraversableEntity
from qq.importers.base_importer import DataSource, EntitySet
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.data_store import DataStore

logger = logging.getLogger(__name__)

# Fields where multiple values should be concatenated/merged rather than
# resolved by priority.
# TODO: figure out how to deal with all names
_LIST_FIELDS = frozenset({"alternative_names", "deprecated_codes"})

# Entity class lookup by class name
_ENTITY_CLASSES: dict[str, type[TraversableEntity]] = {
    "Languoid": Languoid,
    "Script": Script,
    "GeographicRegion": GeographicRegion,
}


def merge(sources: list[tuple[DataSource, EntitySet]], conflicts_path: Path | None = None) -> DataStore:
    """Merge multiple per-source EntitySets into a single DataStore.

    Args:
        sources: List of (DataSource, EntitySet) pairs, ordered by import order.
        conflicts_path: If given, write conflict report JSON to this path.

    Returns:
        The final merged DataStore.
    """
    store = DataStore()
    conflicts: list[dict[str, Any]] = []

    # Collect all entity IDs across all sources
    entity_index: dict[str, type[TraversableEntity]] = {}
    for _source, entity_set in sources:
        for entity in entity_set:
            if entity.id not in entity_index:
                entity_index[entity.id] = type(entity)

    # ---- Pass 1: merge entity attributes ----
    for entity_id, entity_class in entity_index.items():
        # Collect (source_priority, entity) pairs for this ID
        source_entities: list[tuple[DataSource, TraversableEntity]] = []
        for data_source, entity_set in sources:
            entity = entity_set.get(entity_id)
            if entity is not None:
                source_entities.append((data_source, entity))

        # Create the merged entity in the final store
        merged = entity_class(entity_id, store)

        # Merge each data field
        for field_name in entity_class._data_fields:
            merged_value, conflict = _merge_field(field_name, source_entities)
            if merged_value is not None:
                setattr(merged, field_name, merged_value)
            if conflict:
                conflicts.append(conflict)

        store.add(merged)

    # ---- Pass 2: apply relations ----
    _apply_relations(sources, store)

    # ---- Report conflicts ----
    if conflicts:
        logger.warning(f"Total merge conflicts: {len(conflicts)}")
        if conflicts_path:
            with open(conflicts_path, "w") as f:
                json.dump(conflicts, f, indent=2, default=str, ensure_ascii=False)
            logger.info(f"Conflicts saved to {conflicts_path}")
    else:
        logger.info("No merge conflicts found!")

    return store


def _merge_field(
    field_name: str,
    source_entities: list[tuple[DataSource, TraversableEntity]],
) -> tuple[Any, dict[str, Any] | None]:
    """Merge a single field across sources.

    Returns:
        (merged_value, conflict_record or None)
    """
    # Collect non-None values with their source priority
    values: list[tuple[DataSource, Any]] = []
    for data_source, entity in source_entities:
        val = getattr(entity, field_name, None)
        if val is not None:
            values.append((data_source, val))

    if not values:
        return None, None

    if len(values) == 1:
        return values[0][1], None

    # Multiple sources — resolve
    if field_name in _LIST_FIELDS:
        return _merge_list_field(values), None

    # Priority-based: lower DataSource enum value = higher priority
    values.sort(key=lambda pair: pair[0].value)
    winner_source, winner_value = values[0]

    # Check for actual conflict (different values)
    conflict = None
    unique_values = _unique_values([v for _, v in values])
    if len(unique_values) > 1:
        # TODO: make into dataclass?
        conflict = {
            "entity_id": source_entities[0][1].id,
            "field_name": field_name,
            "values": [{"value": v, "source": s.name} for s, v in values],
            "resolved_to": winner_value,
            "strategy": "highest_priority",
        }

    return winner_value, conflict


def _merge_list_field(values: list[tuple[DataSource, Any]]) -> list:
    """Merge list fields by concatenating and deduplicating."""
    merged: list = []
    seen: list = []  # Can't use set for unhashable items
    for _source, val in values:
        items = val if isinstance(val, list) else [val]
        for item in items:
            if item not in seen:
                seen.append(item)
                merged.append(item)
    return merged


def _unique_values(values: list[Any]) -> list[Any]:
    """Count unique values, handling unhashable types like lists."""
    unique: list[Any] = []
    for v in values:
        if v not in unique:
            unique.append(v)
    return unique


def _apply_relations(
    sources: list[tuple[DataSource, EntitySet]],
    store: DataStore,
) -> None:
    """Collect all relations from all EntitySets and apply to final store entities."""
    relations_added = 0
    relations_skipped = 0

    for _data_source, entity_set in sources:
        for entity in entity_set:
            target = store.get(entity.id)
            if target is None:
                continue

            for rel_type, relations in entity._relations.items():
                for rel in relations:
                    # Only add if the target entity exists in the final store
                    if store.get(rel.target_id) is not None:
                        # Avoid duplicate relations
                        existing = target._relations.get(rel_type, [])
                        is_dup = any(r.target_id == rel.target_id and r.metadata == rel.metadata for r in existing)
                        if not is_dup:
                            target.add_relation(rel_type, rel.target_id, **rel.metadata)
                            relations_added += 1
                    else:
                        relations_skipped += 1

    logger.info(f"Applied {relations_added} relations ({relations_skipped} skipped — target not in store)")
