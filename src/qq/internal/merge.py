"""
Merge step: combines per-source EntitySets into a final DataStore.

Pass 1 -> Merge entity attributes:
  For each entity ID across all EntitySets, create one entity in the final
  DataStore. For each field in _data_fields, collect values from all sources.
  Single-source values pass through. Multi-source conflicts resolve by source
  priority (DataSource enum value -> lower = higher priority). Lists are merged.

Pass 2 -> Apply relations:
  Collect all relations from all EntitySets, apply to final store entities
  (only if both source and target exist).
"""

import dataclasses
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from qq.data_model import TraversableEntity
from qq.importers.base_importer import DataSource, EntitySet
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.data_store import DataStore

logger = logging.getLogger(__name__)


@dataclass
class MergeConflict:
    entity_id: str
    field_name: str
    values: list[dict[str, Any]]  # [{"value": ..., "source": ...}, ...]
    resolved_to: Any
    strategy: str


class MergeStrategy(Enum):
    SOURCE_PRIORITY = "source_priority"
    MOST_RECENT = "most_recent"
    MANUAL = "manual"


_FIELD_TO_STRATEGY = {
    # This one is tricky because country / region codes can be deprecated, but
    # still in a transitionary phase. So it's both historical and not.
    # LinguaMeta and pycountry do not agree for 7 values. I check manual
    # resolution and pycountry is more strict with transitional codes, so I
    # interpret Historical as to refer to the ISO codes. Pycountry is also
    # updated more often.
    (GeographicRegion, "is_historical"): (MergeStrategy.MANUAL, DataSource.PYCOUNTRY),
}


# Fields where multiple values should be concatenated/merged rather than
# resolved by priority.
_LIST_FIELDS = frozenset({"deprecated_codes"})

# Fields where conflicts are expected and should not be recorded.
# Name disagreements are irrelevant because multilingual names live in NameDataCache.
_NO_CONFLICT_FIELDS = frozenset({"name"})

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
    conflicts: list[MergeConflict] = []

    # Collect all entity IDs across all sources
    entity_index: dict[str, type[TraversableEntity]] = {}
    for _source, entity_set in sources:
        for entity in entity_set:
            if entity.id not in entity_index:
                entity_index[entity.id] = type(entity)

    # Pass 1: merge entity attributes
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
            merged_value, conflict = _merge_field(field_name, entity_class, source_entities)
            if merged_value is not None:
                setattr(merged, field_name, merged_value)
            if conflict:
                conflicts.append(conflict)

        store.add(merged)

    # Pass 2: apply relations
    _apply_relations(sources, store)

    if conflicts:
        logger.warning(f"Total merge conflicts: {len(conflicts)}")
        if conflicts_path:
            with open(conflicts_path, "w") as f:
                json.dump([dataclasses.asdict(c) for c in conflicts], f, indent=2, default=str, ensure_ascii=False)
            logger.info(f"Conflicts saved to {conflicts_path}")
    else:
        logger.info("No merge conflicts found!")

    return store


def _merge_field(
    field_name: str,
    entity_class: type[TraversableEntity],
    source_entities: list[tuple[DataSource, TraversableEntity]],
) -> tuple[Any, MergeConflict | None]:
    """Merge a single field across sources.

    Returns:
        (merged_value, conflict or None)
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

    # Multiple sources -> resolve
    if field_name in _LIST_FIELDS:
        return _merge_list_field(values), None

    # Default is priority-based: lower DataSource enum value = higher priority
    values.sort(key=lambda pair: pair[0].value)
    winner_source, winner_value = values[0]

    # Some fields have expected disagreements that should not be recorded
    if field_name in _NO_CONFLICT_FIELDS:
        return winner_value, None

    # Check for actual conflict (different values)
    conflict = None
    unique_values = _unique_values([v for _, v in values])
    if len(unique_values) > 1:
        # TODO: this is a bit messy, but per field strategies is also annoying
        # luckily this is only one field at the moment: Region.is_historical
        key = (entity_class, field_name)
        strategy, preferred_source = _FIELD_TO_STRATEGY.get(key, (MergeStrategy.SOURCE_PRIORITY, None))
        if strategy == MergeStrategy.SOURCE_PRIORITY:
            pass  # this is the default anyway above
        elif strategy == MergeStrategy.MANUAL:
            for source, value in values:
                if source == preferred_source:
                    winner_value = value
                    break
            # uncomment for step by step manual resolution through the cli
            # winner_source, winner_value = _manually_resolve_conflict(field_name, values)
        elif strategy == MergeStrategy.MOST_RECENT:
            raise NotImplementedError("Most recent resolution is not implemented yet!")
        else:
            raise ValueError(f"Merge strategy {strategy} is not known.")

        conflict = MergeConflict(
            entity_id=source_entities[0][1].id,
            field_name=field_name,
            values=[{"value": v, "source": s.name} for s, v in values],
            resolved_to=winner_value,
            strategy=strategy.value,
        )

    return winner_value, conflict


def _manually_resolve_conflict(field_name: str, options: list[tuple[DataSource, Any]]) -> tuple[DataSource, Any]:
    import click

    click.echo(f"Conflict detected for: {field_name}")
    for i, (source, val) in enumerate(options, 1):
        click.echo(f"{i}) {source.name} -> {field_name}: {val}")

    choices = [str(i) for i in range(1, len(options) + 1)]
    choice_index = click.prompt("Select the winning value", type=click.Choice(choices), show_choices=True)
    return options[int(choice_index) - 1]


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
                        is_dup = any(r.target_id == rel.target_id for r in existing)
                        if not is_dup:
                            target.add_relation(rel_type, rel.target_id, **rel.metadata)
                            relations_added += 1
                    else:
                        relations_skipped += 1

    logger.info(f"Applied {relations_added} relations ({relations_skipped} skipped -> target not in store)")
