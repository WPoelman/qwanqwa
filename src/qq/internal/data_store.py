from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast, overload

from qq.data_model import CanonicalId, IdType, NameData, TraversableEntity
from qq.internal.names_export import NamesLoader

if TYPE_CHECKING:
    from qq.internal.entity_resolution import EntityResolver

T = TypeVar("T", bound=TraversableEntity)


class DataStore:
    """
    Central storage for all entities with indexing capabilities.
    This acts like a graph database.
    """

    def __init__(self) -> None:
        self._entities: dict[str, TraversableEntity] = {}
        # Index by type for fast all_of_type() lookups
        self._type_index: dict[type, set[str]] = defaultdict(set)
        # Name cache (set by Database for Languoid.name_in())
        self.name_cache: "NameDataCache | None" = None

    def add(self, entity: TraversableEntity) -> None:
        """Add an entity to the store"""
        self._entities[entity.id] = entity
        self._type_index[type(entity)].add(entity.id)

    def get(self, entity_id: str) -> TraversableEntity | None:
        """Get an entity by ID"""
        return self._entities.get(entity_id)

    @overload
    def query(self, entity_type: None = None, **filters) -> list[TraversableEntity]: ...

    @overload
    def query(self, entity_type: type[T], **filters) -> list[T]: ...

    def query(self, entity_type: type[T] | None = None, **filters) -> list[T] | list[TraversableEntity]:
        """
        Query entities with filters.
        Example: store.query(Languoid, speaker_count=lambda x: x > 1000000)
        """
        # Start with set of candidate entity IDs
        if entity_type:
            candidate_ids = self._type_index.get(entity_type, set()).copy()
        else:
            candidate_ids = set(self._entities.keys())

        # Apply attribute filters
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
                        if attr_value is None or not value(attr_value):
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

    Name data (translations of language names) is stored as a zip archive.
    Each per-languoid dict is keyed by the canonical ID of the locale language.

    Accepts an optional resolver to resolve BCP-47 locale codes to canonical
    IDs at runtime (used by name_in() when called with a BCP-47 string).
    """

    def __init__(self, names_path: Path, resolver: "EntityResolver | None" = None):
        self._names_path = names_path
        self._cache: dict[str, dict[CanonicalId, NameData]] = {}
        self._loader = NamesLoader(self._names_path)
        self._resolver = resolver

    def get(self, canonical_id: CanonicalId) -> dict[CanonicalId, NameData] | None:
        """
        Get name data for a specific languoid by its canonical ID.

        Returns a dict mapping locale canonical IDs to NameData objects,
        or None if no name data is available for this languoid.
        """
        if canonical_id in self._cache:
            return self._cache[canonical_id]

        raw_data = self._loader.load_names(canonical_id)
        if not raw_data:
            return None

        parsed: dict[CanonicalId, NameData] = {}
        for entry in raw_data:
            # locale_id is the resolved canonical ID set by resolve_locale_codes().
            # bcp_47_code preserves the original BCP-47 code for readability.
            key = entry.get("locale_id") or entry.get("bcp_47_code") or entry.get("canonical_id")
            if key is None:
                continue
            is_canonical = entry.get("is_canonical") or False
            # When multiple entries share the same locale key, prefer is_canonical=True.
            existing = parsed.get(key)
            if existing is None or (is_canonical and not existing.is_canonical):
                parsed[key] = NameData(
                    name=entry["name"],
                    canonical_id=key,
                    is_canonical=is_canonical,
                )

        self._cache[canonical_id] = parsed
        return parsed

    def get_name_in(self, languoid_id: CanonicalId, locale: str) -> str | None:
        """
        Get the name of a languoid in a specific locale.

        Args:
            languoid_id: Canonical ID of the languoid being named.
            locale: Canonical ID or BCP-47 code of the target locale language.

        Returns:
            Name string, or None if not found.
        """
        name_data = self.get(languoid_id)
        if not name_data:
            return None

        # Direct lookup (already a canonical ID)
        entry = name_data.get(locale)
        if entry:
            return entry.name

        # Try resolving the locale as a BCP-47 code
        if self._resolver:
            canonical = self._resolver.resolve(IdType.BCP_47, locale)
            if canonical:
                entry = name_data.get(canonical)
                if entry:
                    return entry.name

        return None

    def preload(self, canonical_ids: list[CanonicalId]) -> None:
        """Preload name data for multiple languages at once."""
        for canonical_id in canonical_ids:
            self.get(canonical_id)

    def clear_cache(self) -> None:
        """Clear the parsed name data cache."""
        self._cache.clear()
