"""Merge implementation with configured-source provenance."""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from qq.data_model import DataSource, TraversableEntity
from qq.exporters.context import ProvenanceRecord
from qq.importers.base_importer import EntitySet
from qq.interface import GeographicRegion, Script
from qq.internal.data_store import DataStore

logger = logging.getLogger(__name__)


@dataclass
class MergeConflict:
    entity_id: str
    field_name: str
    values: list[dict[str, Any]]
    resolved_to: Any
    strategy: str


@dataclass(frozen=True)
class MergeSource:
    source_name: str
    priority: int
    data_source: DataSource
    entity_set: EntitySet


class MergeStrategy(Enum):
    SOURCE_PRIORITY = "source_priority"
    MOST_RECENT = "most_recent"
    MANUAL = "manual"


_FIELD_TO_STRATEGY = {
    (GeographicRegion, "is_historical"): (MergeStrategy.MANUAL, DataSource.PYCOUNTRY),
}
_LIST_FIELDS = frozenset({"deprecated_codes", "external_resources", "unicode_ranges"})
_NO_CONFLICT_FIELDS = frozenset({"name"})


def normalize_sources(sources: list[MergeSource | tuple[DataSource, EntitySet]]) -> list[MergeSource]:
    normalized = []
    for index, source in enumerate(sources):
        if isinstance(source, MergeSource):
            normalized.append(source)
        else:
            data_source, entity_set = source
            normalized.append(
                MergeSource(
                    source_name=data_source.name.lower(),
                    priority=data_source.value if isinstance(data_source.value, int) else index,
                    data_source=data_source,
                    entity_set=entity_set,
                )
            )
    return normalized


def merge(sources: list[MergeSource | tuple[DataSource, EntitySet]], conflicts_path: Path | None = None) -> DataStore:
    normalized_sources = normalize_sources(sources)
    store = DataStore()
    conflicts: list[MergeConflict] = []
    provenance: list[ProvenanceRecord] = []

    entity_index: dict[str, type[TraversableEntity]] = {}
    for source in normalized_sources:
        for entity in source.entity_set:
            entity_index.setdefault(entity.id, type(entity))

    for entity_id, entity_class in entity_index.items():
        source_entities = [
            (source, entity)
            for source in normalized_sources
            if (entity := source.entity_set.get(entity_id)) is not None
        ]
        merged = entity_class(entity_id, store)
        for field_name in entity_class._data_fields:
            merged_value, conflict, records = _merge_field(field_name, entity_class, source_entities)
            if merged_value is not None:
                setattr(merged, field_name, merged_value)
            if conflict:
                conflicts.append(conflict)
            provenance.extend(records)
        store.add(merged)

    _apply_relations(normalized_sources, store, provenance)
    store.provenance = provenance

    if conflicts and conflicts_path:
        conflicts_path.write_text(
            json.dumps([dataclasses.asdict(c) for c in conflicts], indent=2, default=str, ensure_ascii=False)
        )
    logger.info("Total merge conflicts: %d", len(conflicts))
    return store


def _merge_field(
    field_name: str,
    entity_class: type[TraversableEntity],
    source_entities: list[tuple[MergeSource, TraversableEntity]],
) -> tuple[Any, MergeConflict | None, list[ProvenanceRecord]]:
    values = [
        (source, value)
        for source, entity in source_entities
        if (value := getattr(entity, field_name, None)) is not None
    ]
    if not values:
        return None, None, []

    entity_id = source_entities[0][1].id
    if len(values) == 1:
        source, value = values[0]
        return value, None, [_field_record(entity_id, field_name, source, "selected", value, "single_source")]

    if field_name in _LIST_FIELDS:
        merged = _merge_list_field(values)
        return (
            merged,
            None,
            [
                _field_record(entity_id, field_name, source, "contributor", value, "merge_list")
                for source, value in values
            ],
        )

    values.sort(key=lambda pair: pair[0].priority)
    winner_source, winner_value = values[0]
    if entity_class is Script and field_name == "name":
        for source, value in values:
            if source.data_source == DataSource.PYCOUNTRY:
                winner_source, winner_value = source, value
                break

    unique_values = _unique_values([value for _, value in values])
    conflict = None
    strategy, preferred_source = _FIELD_TO_STRATEGY.get(
        (entity_class, field_name), (MergeStrategy.SOURCE_PRIORITY, None)
    )
    if len(unique_values) > 1 and field_name not in _NO_CONFLICT_FIELDS:
        if strategy == MergeStrategy.MANUAL:
            for source, value in values:
                if source.data_source == preferred_source:
                    winner_source, winner_value = source, value
                    break
        elif strategy == MergeStrategy.MOST_RECENT:
            raise NotImplementedError("Most recent resolution is not implemented")
        conflict = MergeConflict(
            entity_id=entity_id,
            field_name=field_name,
            values=[{"value": value, "source": source.source_name} for source, value in values],
            resolved_to=winner_value,
            strategy=strategy.value,
        )

    records = [
        _field_record(
            entity_id,
            field_name,
            source,
            "selected" if source == winner_source else ("candidate" if conflict else "contributor"),
            value,
            strategy.value,
        )
        for source, value in values
    ]
    return winner_value, conflict, records


def _field_record(
    entity_id: str, field_name: str, source: MergeSource, role: str, value: Any, strategy: str
) -> ProvenanceRecord:
    return ProvenanceRecord(
        kind="field",
        entity_id=entity_id,
        field_name=field_name,
        source_name=source.source_name,
        priority=source.priority,
        role=role,
        strategy=strategy,
        value=value,
    )


def _merge_list_field(values: list[tuple[MergeSource, Any]]) -> list:
    merged: list = []
    for _source, value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item not in merged:
                merged.append(item)
    return merged


def _unique_values(values: list[Any]) -> list[Any]:
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _apply_relations(sources: list[MergeSource], store: DataStore, provenance: list[ProvenanceRecord]) -> None:
    added = skipped = 0
    for source in sources:
        for entity in source.entity_set:
            target = store.get(entity.id)
            if target is None:
                continue
            for relation_type, relations in entity._relations.items():
                for relation in relations:
                    if store.get(relation.target_id) is None:
                        skipped += 1
                        continue
                    existing = target._relations.get(relation_type, [])
                    duplicate = next((item for item in existing if item.target_id == relation.target_id), None)
                    if duplicate is None:
                        target.add_relation(relation_type, relation.target_id, **relation.metadata)
                        added += 1
                    provenance.append(
                        ProvenanceRecord(
                            kind="relation",
                            entity_id=entity.id,
                            relation_type=relation_type.value,
                            target_id=relation.target_id,
                            source_name=source.source_name,
                            priority=source.priority,
                            role="contributor" if duplicate else "selected",
                            strategy="deduplicate",
                            metadata=relation.metadata,
                        )
                    )
    logger.info("Applied %d relations (%d skipped -> target not in store)", added, skipped)
