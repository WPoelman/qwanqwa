from collections import defaultdict
from pathlib import Path
from typing import Any, TypeVar, cast, overload

from qq.data_model import CanonicalId, NameData, TraversableEntity
from qq.internal.names_export import NamesLoader

T = TypeVar("T", bound=TraversableEntity)


class DataStore:
    """
    Central storage for all entities with indexing capabilities.
    This acts like a graph database.
    """

    def __init__(self) -> None:
        self._entities: dict[str, TraversableEntity] = {}
        # Indexes for fast lookups by attribute
        self._indexes: dict[str, dict[Any, set[str]]] = {}
        # Index by type for fast all_of_type() lookups
        self._type_index: dict[type, set[str]] = defaultdict(set)
        # Name cache (set by LanguoidAccess for Languoid.name_in())
        self.name_cache: "NameDataCache | None" = None

    def _add_to_index(self, index_name: str, key: Any, entity_id: str) -> None:
        """Add an entity to a named index."""
        if index_name not in self._indexes:
            self._indexes[index_name] = defaultdict(set)
        self._indexes[index_name][key].add(entity_id)

    def add(self, entity: TraversableEntity) -> None:
        """Add an entity to the store"""
        self._entities[entity.id] = entity
        self._type_index[type(entity)].add(entity.id)

        # TODO: this is annoying, maybe a subclass that handles this? Or allow to register indices?
        # if isinstance(entity, Languoid):
        #     if entity.iso_639_3:
        #         self._add_to_index("iso_639_3", entity.iso_639_3, entity.id)
        #     if entity.glottocode:
        #         self._add_to_index("glottocode", entity.glottocode, entity.id)
        # elif isinstance(entity, Script):
        #     if entity.iso_15924:
        #         self._add_to_index("iso_15924", entity.iso_15924, entity.id)
        # elif isinstance(entity, GeographicRegion):
        #     if entity.parent_country_code:
        #         self._add_to_index("parent_country_code", entity.parent_country_code, entity.id)

    def get(self, entity_id: str) -> TraversableEntity | None:
        """Get an entity by ID"""
        return self._entities.get(entity_id)

    def find_by_attribute(self, attr_name: str, value: Any) -> list[TraversableEntity]:
        """Find entities by indexed attribute"""
        entity_ids = self._indexes.get(attr_name, {}).get(value, set())
        return [self._entities[eid] for eid in entity_ids if eid in self._entities]

    @overload
    def query(self, entity_type: None = None, **filters) -> list[TraversableEntity]: ...

    @overload
    def query(self, entity_type: type[T], **filters) -> list[T]: ...

    def query(self, entity_type: type[T] | None = None, **filters) -> list[T] | list[TraversableEntity]:
        """
        Query entities with filters.
        Example: store.query(Languoid, speaker_count=lambda x: x > 1000000)

        Uses indexes when available for exact match filters on indexed attributes.
        """
        # Start with set of candidate entity IDs
        if entity_type:
            candidate_ids = self._type_index.get(entity_type, set()).copy()
        else:
            candidate_ids = set(self._entities.keys())

        # Apply indexed filters first (most efficient)
        indexed_attrs = set(self._indexes.keys())
        for attr in list(filters.keys()):
            value = filters[attr]
            if not callable(value) and attr in indexed_attrs:
                # Use index and intersect with candidates
                matching_ids = self._indexes[attr].get(value, set())
                candidate_ids &= matching_ids
                del filters[attr]

        # Apply remaining non-indexed filters
        # Only materialize entities now for attribute-based filtering
        if filters:
            filtered_ids = set()
            for eid in candidate_ids:
                entity = self._entities.get(eid)
                if not entity:
                    continue

                matches = True
                for attr, value in filters.items():
                    if not hasattr(entity, attr):
                        matches = False
                        break

                    attr_value = getattr(entity, attr)
                    if callable(value):
                        if not value(attr_value):
                            matches = False
                            break
                    elif attr_value != value:
                        matches = False
                        break

                if matches:
                    filtered_ids.add(eid)

            candidate_ids = filtered_ids

        # Materialize final results
        results = [self._entities[eid] for eid in candidate_ids if eid in self._entities]
        return cast(list[T], results) if entity_type else results

    def all_of_type(self, entity_type: type[T]) -> list[T]:
        """Get all entities of a specific type (uses type index for O(1) lookup)"""
        entity_ids = self._type_index.get(entity_type, set())
        return cast(list[T], [self._entities[eid] for eid in entity_ids if eid in self._entities])


class NameDataCache:
    """
    Lazy loader and cache for language name data.

    Name data (translations of language names) can be stored either as:
    - Individual files in a directory (legacy format)
    - A single zip archive (recommended format)

    This class loads names on-demand per language and caches the results.
    """

    def __init__(self, names_path: Path):
        self._names_path = names_path
        self._cache: dict[str, dict[CanonicalId, NameData]] = {}
        self._loader = NamesLoader(self._names_path)

    def get(self, canonical_id: CanonicalId) -> dict[CanonicalId, NameData] | None:
        """
        Get name data for a specific language by canonical ID.

        Returns a dict mapping canonical IDs to NameData objects,
        or None if no name data is available for this language.
        """
        if canonical_id in self._cache:
            return self._cache[canonical_id]

        raw_data = self._loader.load_names(canonical_id)
        if not raw_data:
            return None

        parsed = {entry["canonical_id"]: NameData(**entry) for entry in raw_data}
        self._cache[canonical_id] = parsed
        return parsed

    def preload(self, canonical_ids: list[CanonicalId]) -> None:
        """Preload name data for multiple languages at once."""
        for canonical_id in canonical_ids:
            self.get(canonical_id)

    def clear_cache(self) -> None:
        """Clear the parsed name data cache."""
        self._cache.clear()
