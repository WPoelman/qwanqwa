import inspect
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, TypeVar, overload

T = TypeVar("T", bound="TraversableEntity")
E = TypeVar("E", bound=Enum)


# TODO: this does not belong here
class DataSource(Enum):
    """Known data sources with priority levels"""

    GLOTTOLOG = 10
    LINGUAMETA = 20
    WIKIDATA = 30
    GLOTSCRIPT = 40
    PYCOUNTRY = 50
    WIKIPEDIA = 60
    SIL = 70


class IdType(Enum):
    """Types of language identifiers"""

    BCP_47 = "bcp_47"
    ISO_639_3 = "iso_639_3"
    # TODO add iso_639_2T even though it's the same as 3?
    ISO_639_2B = "iso_639_2b"
    ISO_639_1 = "iso_639_1"
    GLOTTOCODE = "glottocode"
    WIKIDATA_ID = "wikidata_id"


# Type alias for canonical entity IDs (e.g., "lang:000001", "script:0001")
CanonicalId = str

# Mapping from IdType to Languoid attribute names
# TODO check if this can be removed, this is bit stupid
ID_TYPE_TO_ATTR: dict["IdType", str] = {
    IdType.BCP_47: "bcp_47",
    IdType.ISO_639_3: "iso_639_3",
    IdType.ISO_639_2B: "iso_639_2b",
    IdType.ISO_639_1: "iso_639_1",
    IdType.GLOTTOCODE: "glottocode",
    IdType.WIKIDATA_ID: "wikidata_id",
}


@dataclass
class DeprecatedCode:
    """A deprecated/retired identifier that formerly referred to this languoid."""

    code: str
    code_type: str  # "iso_639_3" or "bcp_47"
    reason: str | None = None  # C=Change, M=Merge, D=Duplicate, S=Split, N=Non-existent
    name: str | None = None  # Original reference name from retirements table
    effective: str | None = None  # Date retired (YYYY-MM-DD)
    remedy: str | None = None  # Description of what happened


@dataclass
class WikipediaInfo:
    """Wikipedia edition metadata for a language."""

    url: str | None = None
    code: str | None = None
    article_count: int | None = None
    active_users: int | None = None


@dataclass
class NameData:
    """Name data for a languoid in a specific locale."""

    name: str
    canonical_id: str
    is_canonical: bool = False


class RelationType(Enum):
    """Types of relationships between entities in qq."""

    # Phylogenetic (languoid tree)
    PARENT_LANGUOID = "parent"
    CHILD_LANGUOID = "child"

    # Geographic
    SPOKEN_IN_REGION = "spoken_in"
    LANGUOIDS_IN_REGION = "languoids_in"

    # Writing systems
    USES_SCRIPT = "uses_script"
    USED_BY_LANGUOID = "used_by"

    # Macrolanguage
    MACROLANGUAGE_OF = "macrolanguage_of"
    INDIVIDUAL_LANGUAGE_OF = "individual_language_of"

    # Geographic hierarchy
    IS_PART_OF = "is_part_of"  # For subdivisions -> countries
    HAS_CHILD_REGION = "has_child_region"


@dataclass
class Relation:
    """Represents a relationship between two entities"""

    relation_type: RelationType
    target_id: CanonicalId  # ID of the related entity, to know the source entity, it's the one you get this from
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"{self.relation_type.value} -> {self.target_id}"


# TODO: possibly merge level, scope and status?
class LanguoidLevel(Enum):
    """
    Languoid classification level from Glottolog.

    A languoid is any node in the language phylogenetic tree. This enum indicates
    what type of node it is: a language family, an individual language, or a dialect.
    """

    LANGUAGE = "language"  # Individual language
    DIALECT = "dialect"  # Dialect of a language
    FAMILY = "family"  # Language family (group of related languages)


class LanguageScope(Enum):
    """
    ISO 639-3 scope classification.

    Indicates whether a code represents an individual language, macrolanguage, or special case.
    """

    INDIVIDUAL = "I"
    MACROLANGUAGE = "M"
    SPECIAL = "S"


class LanguageStatus(Enum):
    """
    ISO 639-3 language status/type.

    Indicates whether a language is living, historical, extinct, etc.
    """

    LIVING = "L"
    HISTORICAL = "H"
    ANCIENT = "A"
    CONSTRUCTED = "C"
    EXTINCT = "E"
    SPECIAL = "S"


class EndangermentStatus(Enum):
    """
    Language endangerment status from UNESCO/LinguaMeta.

    Follows the UNESCO endangerment scale, from safe to extinct.
    """

    NOT_ENDANGERED = "Not endangered"
    VULNERABLE = "Vulnerable"
    DEFINITELY_ENDANGERED = "Definitely endangered"
    SEVERELY_ENDANGERED = "Severely endangered"
    CRITICALLY_ENDANGERED = "Critically endangered"
    EXTINCT = "Extinct"


class EntityContainer(Protocol):
    """Protocol for anything that stores entities by ID (DataStore or EntitySet)."""

    def get(self, entity_id: str) -> "TraversableEntity | None": ...


class TraversableEntity:
    """
    Base class for all entities that can be traversed.
    Provides graph-like navigation capabilities.

    This might be a bit over-engineered... TODO: simplify
    """

    _data_fields: frozenset[str] = frozenset()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        sig = inspect.signature(cls.__init__)
        cls._data_fields = frozenset(name for name in sig.parameters if name not in ("self", "entity_id", "data_store"))

    def __init__(self, entity_id: str, data_store: "EntityContainer") -> None:
        self.id: str = entity_id
        self._store: "EntityContainer" = data_store
        self._relations: dict[RelationType, list[Relation]] = defaultdict(list)

    def add_relation(self, relation_type: RelationType, target_id: str, **metadata: Any) -> None:
        """Add a relationship to another entity"""
        relation = Relation(relation_type, target_id, metadata)
        self._relations[relation_type].append(relation)

    # TODO: Not sure if it belongs here, but it makes sense in the workflow above
    @staticmethod
    def _to_enum(value: E | str | None, enum_class: type[E]) -> E | None:
        """Convert a string to enum if needed, or return None/enum as-is."""
        if value is None:
            return None
        if isinstance(value, enum_class):
            return value
        if isinstance(value, str):
            try:
                return enum_class(value)
            except ValueError:
                return None
        return None

    @overload
    def get_related(self, relation_type: RelationType, entity_class: None = None) -> list["TraversableEntity"]: ...

    @overload
    def get_related(self, relation_type: RelationType, entity_class: type[T]) -> list[T]: ...

    def get_related(
        self, relation_type: RelationType, entity_class: type[T] | None = None
    ) -> list[T] | list["TraversableEntity"]:
        """Get all entities related by a specific relation type."""
        relations = self._relations.get(relation_type, [])
        entities = []

        for rel in relations:
            entity = self._store.get(rel.target_id)
            if entity:
                if entity_class is None or isinstance(entity, entity_class):
                    entities.append(entity)

        return entities
