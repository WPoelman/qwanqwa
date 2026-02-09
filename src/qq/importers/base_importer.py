import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    errors: list[str] = field(default_factory=list)


class EntitySet:
    """
    Lightweight import container — one per importer.

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
        canonical_id = self.resolver.find_or_create_canonical_id(identifiers)
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

    def _sync_identifiers_to_entity(self, entity: Languoid, identity: EntityIdentity):
        """Sync all identifiers from identity to entity attributes"""
        for id_type, attr_name in ID_TYPE_TO_ATTR.items():
            value = identity.get_identifier(id_type)
            if value and not getattr(entity, attr_name, None):
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
        **metadata,
    ):
        """
        Add bidirectional relationship between two entities.
        Metadata is available on both directions.
        """
        entity1.add_relation(rel_type1, entity2.id, **metadata)
        entity2.add_relation(rel_type2, entity1.id, **metadata)
        self.stats.relations_added += 2

    def log_stats(self):
        """Log import statistics"""
        logger.info(f"{self.__class__.__name__} Statistics:")
        logger.info(f"  Created: {self.stats.entities_created}")
        logger.info(f"  Updated: {self.stats.entities_updated}")
        logger.info(f"  Relations: {self.stats.relations_added}")
        if self.stats.errors:
            logger.warning(f"  Errors: {len(self.stats.errors)}")
