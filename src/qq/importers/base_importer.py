import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

from qq.data_model import ID_TYPE_TO_ATTR, DataSource, IdType, RelationType, TraversableEntity
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.entity_resolution import EntityIdentity, EntityResolver

# An importer generates entities that populate the final graph.
# The order is Source -> Importer -> Merge -> Link
# Download or define a source, import useful information, merge results from all importers -> link entities

T = TypeVar("T", bound=TraversableEntity)

logger = logging.getLogger(__name__)


@dataclass
class ImportStats:
    entities_created: int = 0
    entities_updated: int = 0
    relations_added: int = 0


class EntitySet:
    """
    Lightweight import container: one per importer.

    Holds entities produced during a single import phase. Entities reference
    this as their ``_store`` (they only need ``get()``; traversal properties
    aren't used during import).
    """

    def __init__(self) -> None:
        self._entities: dict[str, TraversableEntity] = {}

    def add(self, entity: TraversableEntity) -> None:
        """Add an entity to the set."""
        self._entities[entity.id] = entity

    def get(self, entity_id: str) -> TraversableEntity | None:
        """Get an entity by ID."""
        return self._entities.get(entity_id)

    def __iter__(self):
        return iter(self._entities.values())

    def __len__(self) -> int:
        return len(self._entities)

    def __contains__(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def entities_of_type(self, entity_type: type[T]) -> list[T]:
        """Get all entities of a specific type."""
        return cast(list[T], [e for e in self._entities.values() if isinstance(e, entity_type)])

    def merge_entity_ids(self, source_id: str, target_id: str) -> TraversableEntity | None:
        """Collapse one entity ID into another and rewrite relations."""
        if source_id == target_id:
            return self.get(target_id)

        source = self._entities.get(source_id)
        target = self._entities.get(target_id)

        if source is None:
            return target

        if target is None:
            del self._entities[source_id]
            source.id = target_id
            self._entities[target_id] = source
            self._rewrite_relation_targets(source_id, target_id)
            return source

        if type(source) is not type(target):
            raise TypeError(f"Cannot merge {type(source).__name__} into {type(target).__name__}")

        for attr, value in source.__dict__.items():
            if attr.startswith("_") or attr == "id":
                continue
            if getattr(target, attr, None) is None and value is not None:
                setattr(target, attr, value)

        for rel_type, relations in source._relations.items():
            existing = target._relations.setdefault(rel_type, [])
            existing_keys = {(rel.target_id, tuple(sorted(rel.metadata.items()))) for rel in existing}
            for rel in relations:
                key = (rel.target_id, tuple(sorted(rel.metadata.items())))
                if key not in existing_keys:
                    existing.append(rel)
                    existing_keys.add(key)

        del self._entities[source_id]
        self._rewrite_relation_targets(source_id, target_id)
        return target

    def _rewrite_relation_targets(self, source_id: str, target_id: str) -> None:
        """Rewrite relation targets after an entity ID changes."""
        for entity in self._entities.values():
            for relations in entity._relations.values():
                for rel in relations:
                    if rel.target_id == source_id:
                        rel.target_id = target_id


class BaseImporter(ABC):
    """
    Base class for all data importers.

    Each importer produces entities into an EntitySet.
    The merge step later combines all EntitySets into the final DataStore.
    """

    source: DataSource

    def __init__(self, resolver: EntityResolver):
        self.resolver = resolver
        self.entity_set = EntitySet()
        self.stats = ImportStats()
        if self.source is None:
            raise ValueError("Subclasses should register which source they are.")

    @abstractmethod
    def import_data(self, data_path: Path) -> None:
        """Import data from the given path"""
        pass

    def get_or_create_languoid(self, identifiers: dict[IdType, str]) -> Languoid:
        """
        Get existing languoid or create new one in this importer's EntitySet.
        Uses entity resolution to handle multiple IDs.

        Args:
            identifiers: Dict of identifier types and values
                         e.g., {IdType.ISO_639_3: 'nld', IdType.GLOTTOCODE: 'dutc1256'}
        """
        previous_ids = {
            canonical_id
            for id_type, value in identifiers.items()
            if (canonical_id := self.resolver.resolve(id_type, value)) is not None
        }
        canonical_id = self.resolver.find_or_create_canonical_id(identifiers)
        for previous_id in previous_ids:
            if previous_id != canonical_id:
                self.entity_set.merge_entity_ids(previous_id, canonical_id)
        identity = self.resolver.get_identity(canonical_id)
        if not identity:
            raise ValueError("This should not be possible. Cannot find identity for Entity.")
        entity = self.entity_set.get(canonical_id)
        if entity and isinstance(entity, Languoid):
            self.stats.entities_updated += 1
            self._sync_identifiers_to_entity(entity, identity)
            return entity

        self.stats.entities_created += 1
        kwargs = self._identifiers_to_kwargs(identity)
        languoid = Languoid(canonical_id, self.entity_set, **kwargs)
        self.entity_set.add(languoid)
        return languoid

    def resolve_languoid(self, id_type: IdType, value: str) -> Languoid | None:
        """Look up a canonical ID via the resolver and create a stub entity if found.

        Used by enrichment importers that need to reference an entity from
        another source by one of its identifiers.
        """
        canonical_id = self.resolver.resolve(id_type, value)
        if not canonical_id:
            return None

        entity = self.entity_set.get(canonical_id)
        if entity and isinstance(entity, Languoid):
            return entity

        identity = self.resolver.get_identity(canonical_id)
        kwargs = self._identifiers_to_kwargs(identity) if identity else {}
        languoid = Languoid(canonical_id, self.entity_set, **kwargs)
        self.entity_set.add(languoid)
        self.stats.entities_created += 1
        return languoid

    def _sync_identifiers_to_entity(self, entity: Languoid, identity: EntityIdentity) -> None:
        """Sync identifiers from identity to entity, skipping already-set attributes."""
        for attr_name, value in self._identifiers_to_kwargs(identity).items():
            if not getattr(entity, attr_name, None):
                setattr(entity, attr_name, value)

    def _identifiers_to_kwargs(self, identity: EntityIdentity) -> dict[str, Any]:
        """Build kwargs dict from identity identifiers."""
        kwargs: dict[str, Any] = {}
        for id_type, attr_name in ID_TYPE_TO_ATTR.items():
            value = identity.get_identifier(id_type)
            if value:
                kwargs[attr_name] = value
        return kwargs

    def _get_or_create_entity(self, entity_id: str, entity_class: type[T]) -> T:
        """Get existing entity or create new one in our EntitySet."""
        entity = self.entity_set.get(entity_id)
        if entity and isinstance(entity, entity_class):
            self.stats.entities_updated += 1
            return entity

        self.stats.entities_created += 1
        new_entity = entity_class(entity_id, self.entity_set)
        self.entity_set.add(new_entity)
        return new_entity

    def get_or_create_script(self, script_id: str) -> Script:
        """Get existing script or create new one."""
        return self._get_or_create_entity(script_id, Script)

    def get_or_create_region(self, region_id: str) -> GeographicRegion:
        """Get existing region or create new one."""
        return self._get_or_create_entity(region_id, GeographicRegion)

    def add_bidirectional_relation(
        self,
        entity1: TraversableEntity,
        rel_type1: RelationType,
        entity2: TraversableEntity,
        rel_type2: RelationType,
        **metadata: Any,
    ):
        entity1.add_relation(rel_type1, entity2.id, **metadata)
        entity2.add_relation(rel_type2, entity1.id, **metadata)
        self.stats.relations_added += 2

    def log_stats(self):
        """Log import statistics"""
        logger.info(f"{self.__class__.__name__} Statistics:")
        logger.info(f"  Created: {self.stats.entities_created}")
        logger.info(f"  Updated: {self.stats.entities_updated}")
        logger.info(f"  Relations: {self.stats.relations_added}")
