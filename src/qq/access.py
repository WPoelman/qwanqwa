from __future__ import annotations

import warnings
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from qq.constants import DEFAULT_DB_PATH
from qq.data_model import ID_TYPE_TO_ATTR, CanonicalId, IdType, LanguoidLevel, NameData
from qq.interface import GeographicRegion, Languoid, Script

if TYPE_CHECKING:
    from qq.data_model import TraversableEntity
    from qq.interface import GeographicRegion, Languoid, Script
    from qq.internal.data_store import DataStore
    from qq.internal.entity_resolution import EntityResolver

T = TypeVar("T")


class DeprecatedCodeWarning(UserWarning):
    """Warning issued when a deprecated/retired language code is used."""

    pass


class IdConversion:
    """Convert between different language identifier types."""

    def __init__(self, store: DataStore, resolver: EntityResolver) -> None:
        self.store = store
        self.resolver = resolver

    def convert(self, code: str, from_type: IdType, to_type: IdType) -> str | None:
        """
        Convert a code from one identifier type to another.

        Args:
            code: The identifier code to convert
            from_type: The source identifier type
            to_type: The target identifier type

        Returns:
            The converted code, or None if not found

        Example:
            >>> ic.convert("nl", IdType.BCP_47, IdType.ISO_639_3)
            'nld'
        """
        canonical_id = self.resolver.resolve(from_type, code)
        if not canonical_id:
            return None

        entity = self.store.get(canonical_id)
        if not entity:
            return None

        attr_name = ID_TYPE_TO_ATTR.get(to_type)
        if not attr_name:
            return None

        return getattr(entity, attr_name, None)


class Database:
    """
    Unified access point for all linguistic data: languoids, scripts, and
    geographic regions.

    Basic usage:
        >>> db = Database.load()
        >>> dutch = db.get("nl")
        >>> latin = db.get_script("Latn")
        >>> netherlands = db.get_region("NL")

    Querying:
        >>> db.query(Languoid, speaker_count=lambda n: n > 1_000_000)
        >>> db.query(Script, is_historical=False)
        >>> db.query(GeographicRegion, country_code="NL")
    """

    def __init__(self, store: DataStore, resolver: EntityResolver, names_path: Path | None = None) -> None:
        self.store = store
        self.resolver = resolver
        self._id_conversion = IdConversion(self.store, self.resolver)

        if names_path and names_path.exists():
            from qq.internal.data_store import NameDataCache

            self.store.name_cache = NameDataCache(names_path, resolver=resolver)

    @property
    def id_conversion(self) -> IdConversion:
        """Get the ID conversion helper for converting between identifier types."""
        return self._id_conversion

    @classmethod
    def load(cls, path: Path = DEFAULT_DB_PATH, names_path: Path | None = None) -> Database:
        """
        Load the database from disk.

        Args:
            path: Path to main database file (default: bundled db.json.gz)
            names_path: Path to names.zip; auto-detected next to the database if omitted
        """
        from qq.internal.storage import load_data

        store, resolver = load_data(path)

        if names_path is None:
            default_names = path.parent / "names.zip"
            if default_names.exists():
                names_path = default_names

        return cls(store, resolver, names_path)

    def get(self, code: str, id_type: IdType = IdType.BCP_47) -> Languoid:
        """
        Get a languoid by identifier.

        Args:
            code: Language identifier (e.g., "nl", "nld", "dutc1256")
            id_type: Type of identifier (default: BCP_47)

        Raises:
            KeyError: If not found

        Example:
            >>> db.get("nl")
            >>> db.get("nld", IdType.ISO_639_3)
        """
        from qq.interface import Languoid

        canonical_id = self.resolver.resolve(id_type, code)
        if not canonical_id:
            if self.resolver.is_deprecated(id_type, code):
                reason = self.resolver._deprecated_codes.get((id_type, code), "")
                raise KeyError(
                    f"Code '{code}' ({id_type.value}) is deprecated/retired ({reason}) and has no single replacement."
                )
            raise KeyError(f"Languoid for code {code} ({id_type.value}) not found.")

        entity = self.store.get(canonical_id)
        if entity and isinstance(entity, Languoid):
            if self.resolver.is_deprecated(id_type, code):
                warnings.warn(
                    f"Code '{code}' ({id_type.value}) is deprecated. "
                    f"Resolved to: {entity.name} ({entity.iso_639_3 or entity.bcp_47})",
                    DeprecatedCodeWarning,
                    stacklevel=2,
                )
            return entity
        raise KeyError(f"Languoid for code {code} ({id_type.value}) not found.")

    def guess(self, code: str) -> Languoid:
        """
        Try to find a languoid by checking all known identifier types.

        Use with caution: the same string may exist in multiple identifier systems.

        Raises:
            KeyError: If not found with any identifier type
        """
        deprecated_error = None
        for id_type in IdType:
            try:
                return self.get(code, id_type)
            except KeyError as e:
                if deprecated_error is None and "deprecated" in str(e):
                    deprecated_error = e
        if deprecated_error is not None:
            raise deprecated_error
        raise KeyError(f"Languoid for code {code} not found for any known identifier type.")

    def convert(self, code: str, from_type: IdType, to_type: IdType) -> str | None:
        """
        Convert a language code from one identifier type to another.

        Returns:
            Converted code, or None if not found

        Example:
            >>> db.convert("nl", IdType.BCP_47, IdType.ISO_639_3)
            'nld'
        """
        return self._id_conversion.convert(code, from_type, to_type)

    def get_names(self, code: str, id_type: IdType = IdType.BCP_47) -> dict[CanonicalId, NameData] | None:
        """
        Get name translations for a language.

        Returns a dict mapping locale canonical IDs to NameData, or None if
        the names database is not loaded.

        Example:
            >>> french = db.get("fr")
            >>> names = db.get_names("nl")
            >>> names[french.id].name  # "néerlandais"
        """
        if not self.store.name_cache:
            return None

        canonical_id = self.resolver.resolve(id_type, code)
        if not canonical_id:
            return None

        return self.store.name_cache.get(canonical_id)

    def search(self, query: str, limit: int = 20) -> list[Languoid]:
        """
        Search for languoids by name (case-insensitive partial match).

        Searches both the primary name and endonym.

        Example:
            >>> db.search("dutch")
            [Languoid(Dutch), Languoid(Middle Dutch), ...]
        """
        from qq.interface import Languoid

        if not hasattr(self, "_name_index"):
            self._build_name_index()

        query_lower = query.lower()
        results = []
        seen: set[str] = set()

        for name_lower, entity_ids in self._name_index.items():
            if query_lower in name_lower:
                for entity_id in entity_ids:
                    if entity_id not in seen:
                        entity = self.store.get(entity_id)
                        if entity and isinstance(entity, Languoid):
                            results.append(entity)
                            seen.add(entity_id)
                            if len(results) >= limit:
                                return results

        return results

    def is_deprecated(self, code: str, id_type: IdType | None = None) -> bool:
        """Check if a code is deprecated/retired.

        Args:
            code: Language identifier to check
            id_type: Specific identifier type, or None to check all types
        """
        if id_type is not None:
            return self.resolver.is_deprecated(id_type, code)
        return any(self.resolver.is_deprecated(t, code) for t in IdType)

    @property
    def all_languoids(self) -> list[Languoid]:
        """All languoids (families, languages, and dialects)."""

        return self.store.all_of_type(Languoid)

    @property
    def all_languages(self) -> list[Languoid]:
        """All individual languages (level=LANGUAGE)."""

        return [lang for lang in self.store.all_of_type(Languoid) if lang.level == LanguoidLevel.LANGUAGE]

    @property
    def all_families(self) -> list[Languoid]:
        """All language families (level=FAMILY)."""

        return [lang for lang in self.store.all_of_type(Languoid) if lang.level == LanguoidLevel.FAMILY]

    @property
    def all_dialects(self) -> list[Languoid]:
        """All dialects (level=DIALECT)."""

        return [lang for lang in self.store.all_of_type(Languoid) if lang.level == LanguoidLevel.DIALECT]

    def get_script(self, code: str) -> Script:
        """
        Get a script by ISO 15924 code (e.g., "Latn", "Arab", "Cyrl").

        Raises:
            KeyError: If not found
        """
        script_id = f"script:{code.lower()}"
        entity = self.store.get(script_id)
        if entity and isinstance(entity, Script):
            return entity
        raise KeyError(f"Script '{code}' not found.")

    def search_scripts(self, query: str, limit: int = 20) -> list[Script]:
        """
        Search for scripts by name (case-insensitive partial match).

        Searches both short name and full name.

        Example:
            >>> db.search_scripts("latin")
            [Script(Latin, code=Latn)]
        """
        query_lower = query.lower()
        results = []
        for script in self.store.all_of_type(Script):
            if (script.name and query_lower in script.name.lower()) or (
                script.full_name and query_lower in script.full_name.lower()
            ):
                results.append(script)
                if len(results) >= limit:
                    break
        return results

    @property
    def all_scripts(self) -> list[Script]:
        """All writing system scripts."""
        return self.store.all_of_type(Script)

    def get_region(self, code: str) -> GeographicRegion:
        """
        Get a geographic region by country code (e.g., "NL", "US", "CN").

        Raises:
            KeyError: If not found
        """
        region_id = f"region:{code.lower()}"
        entity = self.store.get(region_id)
        if entity and isinstance(entity, GeographicRegion):
            return entity
        raise KeyError(f"Region '{code}' not found.")

    def search_regions(self, query: str, limit: int = 20) -> list[GeographicRegion]:
        """
        Search for regions by name or country code (case-insensitive partial match).

        Example:
            >>> db.search_regions("nether")
            [GeographicRegion(Netherlands)]
        """
        query_lower = query.lower()
        results = []
        for region in self.store.all_of_type(GeographicRegion):
            if (region.name and query_lower in region.name.lower()) or (
                region.country_code and query_lower in region.country_code.lower()
            ):
                results.append(region)
                if len(results) >= limit:
                    break
        return results

    @property
    def all_regions(self) -> list[GeographicRegion]:
        """All geographic regions (countries, subdivisions, and historical)."""
        return self.store.all_of_type(GeographicRegion)

    @property
    def all_countries(self) -> list[GeographicRegion]:
        """
        All current top-level countries (excludes subdivisions and historical countries).
        """
        return [
            r
            for r in self.store.all_of_type(GeographicRegion)
            if r.country_code is not None and r.parent_country_code is None and not r.is_historical
        ]

    def query(self, entity_type: type[TraversableEntity], **filters: Any) -> list[Any]:
        """
        Filter entities by attribute values or callable predicates.

        Args:
            entity_type: Entity class to search (Languoid, Script, GeographicRegion).
                         Defaults to Languoid.
            **filters: Attribute name -> value (equality) or callable (predicate)

        Example:
            >>> db.query(Languoid, speaker_count=lambda n: n > 1_000_000)
            >>> db.query(Script, is_historical=False)
            >>> db.query(GeographicRegion, country_code="NL")
        """
        return self.store.query(entity_type, **filters)

    def _build_name_index(self) -> None:
        """Build a lowercase name -> [entity_id] index for fast languoid search."""

        self._name_index: dict[str, list[str]] = defaultdict(list)

        for lang in self.store.all_of_type(Languoid):
            if lang.name:
                self._name_index[lang.name.lower()].append(lang.id)
            if lang.endonym:
                self._name_index[lang.endonym.lower()].append(lang.id)
