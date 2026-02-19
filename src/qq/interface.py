from qq.data_model import (
    DeprecatedCode,
    EndangermentStatus,
    EntityContainer,
    LanguageScope,
    LanguageStatus,
    LanguoidLevel,
    RelationType,
    TraversableEntity,
    WikipediaInfo,
)
from qq.internal.data_store import DataStore

# These are the main classes the user is expected to interact with
# They should be directly available from the main qq import
__all__ = ["Languoid", "Script", "GeographicRegion"]


class Languoid(TraversableEntity):
    """
    A Languoid is a language-like entity (dialect, language, macro language, or language family).

    Languoids support graph-like traversal for exploring relationships between languages,
    scripts, and regions. This is the primary interface for working with language data.

    Basic usage:
        >>> from qq import Database
        >>> access = Database.load()
        >>> dutch = access.get("nl")
        >>> print(dutch.name, dutch.iso_639_3, dutch.speaker_count)
        Dutch nld 24000000

    Accessing identifiers:
        >>> dutch.bcp_47           # "nl"
        >>> dutch.iso_639_3        # "nld"
        >>> dutch.iso_639_1        # "nl"
        >>> dutch.glottocode       # "dutc1256"
        >>> dutch.wikidata_id      # "Q7411"
        >>> dutch.wikipedia.code   # "nl"  (Wikipedia language edition code)

    Looking up by Wikipedia code:
        >>> access.get("nl", IdType.WIKIPEDIA)       # Dutch (standard code)
        >>> access.get("zh-yue", IdType.WIKIPEDIA)   # Cantonese (compound code)
        >>> access.get("simple", IdType.WIKIPEDIA)   # English (Simple English alias)

    Phylogenetic navigation:
        >>> dutch.parent                    # West Germanic
        >>> dutch.parent.parent             # Germanic
        >>> dutch.family_tree               # All ancestors up to root
        >>> dutch.children                  # [Flemish, Afrikaans, ...]
        >>> dutch.siblings                  # [English, German, Frisian, ...]
        >>> dutch.descendants(limit=None)   # All descendants (recursive)

    Cross-domain traversal:
        >>> dutch.scripts                   # [Script(Latin, code=Latn)]
        >>> dutch.script_codes              # ["Latn"]
        >>> dutch.regions                   # [Netherlands, Belgium, Suriname, ...]
        >>> dutch.name_in("fr")             # "néerlandais"
        >>> dutch.name_in(french)           # works with Languoids as well -> "néerlandais"
        >>> dutch.nllb_codes()              # ["nld_Latn"]

    Attributes:
        bcp_47: BCP-47 language code (e.g., "nl", "zh-Hans")
        iso_639_3: ISO 639-3 code (e.g., "nld")
        iso_639_2t: ISO 639-2T (terminological) code (always identical to iso_639_3)
        iso_639_2b: ISO 639-2B code (e.g., "dut")
        glottocode: Glottolog code (e.g., "dutc1256")
        wikidata_id: Wikidata identifier (e.g., "Q7411")
        name: Primary name (typically in English)
        endonym: Name in the language itself
        speaker_count: Number of speakers
        latitude: Geographic latitude
        longitude: Geographic longitude
        level: Glottolog level (language/dialect/family)
        scope: ISO 639-3 scope (I/M/S)
        status: ISO 639-3 type (L/H/A/C/E/S)
        endangerment_status: UNESCO endangerment classification
        wikipedia: WikipediaInfo with edition metadata (code, url, article_count, active_users)
        description: Textual description
    """

    def __init__(
        self,
        entity_id: str,
        data_store: EntityContainer,
        # Core identifiers, see IdType for more information
        bcp_47: str | None = None,
        iso_639_1: str | None = None,
        iso_639_2b: str | None = None,
        iso_639_3: str | None = None,
        iso_639_5: str | None = None,
        glottocode: str | None = None,
        wikidata_id: str | None = None,
        # Names
        name: str | None = None,
        endonym: str | None = None,
        # Population/speakers
        speaker_count: int | None = None,
        # Geographic coordinates
        latitude: float | None = None,
        longitude: float | None = None,
        # Classification (from Glottolog and ISO 639-3)
        level: LanguoidLevel | str | None = None,
        scope: LanguageScope | str | None = None,
        status: LanguageStatus | str | None = None,
        endangerment_status: EndangermentStatus | str | None = None,
        # Wikipedia metadata (grouped)
        wikipedia: WikipediaInfo | None = None,
        # Description
        description: str | None = None,
        # Deprecated/retired codes
        deprecated_codes: list[DeprecatedCode] | None = None,
    ) -> None:
        super().__init__(entity_id, data_store)

        # Core identifiers
        self.bcp_47: str | None = bcp_47
        self.iso_639_1: str | None = iso_639_1
        self.iso_639_2b: str | None = iso_639_2b
        self.iso_639_3: str | None = iso_639_3
        self.iso_639_5: str | None = iso_639_5
        self.glottocode: str | None = glottocode
        self.wikidata_id: str | None = wikidata_id

        # Names
        self.name: str | None = name
        self.endonym: str | None = endonym

        # Population/speakers
        self.speaker_count: int | None = speaker_count

        # Geographic coordinates
        self.latitude: float | None = latitude
        self.longitude: float | None = longitude

        # Classification (convert strings to enums if needed)
        self.level: LanguoidLevel | None = self._to_enum(level, LanguoidLevel)
        self.scope: LanguageScope | None = self._to_enum(scope, LanguageScope)
        self.status: LanguageStatus | None = self._to_enum(status, LanguageStatus)
        self.endangerment_status: EndangermentStatus | None = self._to_enum(endangerment_status, EndangermentStatus)

        # Wikipedia metadata (grouped)
        self.wikipedia: WikipediaInfo | None = wikipedia

        # Description
        self.description: str | None = description

        # Deprecated/retired codes
        self.deprecated_codes: list[DeprecatedCode] | None = deprecated_codes

    @property
    def iso_639_2t(self) -> str | None:
        """ISO 639-2T (terminological) code. Always identical to iso_639_3."""
        return self.iso_639_3

    @property
    def parent(self) -> "Languoid | None":
        """Get parent languoid (if any)."""
        parents = self.get_related(RelationType.PARENT_LANGUOID, Languoid)
        return parents[0] if parents else None

    @property
    def children(self) -> list["Languoid"]:
        """Get all child languoids."""
        return self.get_related(RelationType.CHILD_LANGUOID, Languoid)

    @property
    def siblings(self) -> list["Languoid"]:
        """Get sibling languoids (same parent)."""
        if self.parent is None:
            return []
        return [child for child in self.parent.children if child.id != self.id]

    @property
    def family_tree(self) -> list["Languoid"]:
        """Get all ancestors up to root family."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    @property
    def root_family(self) -> "Languoid | None":
        """Get the root family (top of the family_tree)."""
        return self.family_tree[-1] if self.family_tree else None

    @property
    def is_language(self) -> bool:
        """Check if this is an individual language (not a dialect or family)."""
        return self.level == LanguoidLevel.LANGUAGE

    @property
    def is_dialect(self) -> bool:
        """Check if this is a dialect."""
        return self.level == LanguoidLevel.DIALECT

    @property
    def is_family(self) -> bool:
        """Check if this is a language family."""
        return self.level == LanguoidLevel.FAMILY

    @property
    def is_macrolanguage(self) -> bool:
        """Check if this is a macrolanguage (derived from scope)."""
        return self.scope == LanguageScope.MACROLANGUAGE

    @property
    def macrolanguage(self) -> "Languoid | None":
        """Get the macrolanguage this languoid belongs to (if any)."""
        parents = self.get_related(RelationType.INDIVIDUAL_LANGUAGE_OF, Languoid)
        return parents[0] if parents else None

    @property
    def individual_languages(self) -> list["Languoid"]:
        """Get individual languages belonging to this macrolanguage."""
        return self.get_related(RelationType.MACROLANGUAGE_OF, Languoid)

    @property
    def scripts(self) -> list["Script"]:
        """Get all scripts used by this languoid."""
        return self.get_related(RelationType.USES_SCRIPT, Script)

    @property
    def script_codes(self) -> list[str] | None:
        """Get list of script codes (ISO 15924) used by this languoid."""
        script_entities = self.scripts
        if not script_entities:
            return None
        seen: dict[str, None] = {}
        for s in script_entities:
            if s.iso_15924:
                seen[s.iso_15924] = None
        return list(seen) if seen else None

    @property
    def canonical_scripts(self) -> list["Script"]:
        """
        Get canonical (primary) scripts used by this languoid.

        Returns scripts marked as canonical in the linguameta data (via relation metadata).
        For languoids without canonical script metadata, returns all scripts.
        """
        canonical: list[Script] = []
        relations = self._relations.get(RelationType.USES_SCRIPT, [])

        for rel in relations:
            if rel.metadata.get("is_canonical", False):
                script = self._store.get(rel.target_id)
                if script and isinstance(script, Script):
                    canonical.append(script)

        return canonical if canonical else self.scripts

    @property
    def regions(self) -> list["GeographicRegion"]:
        """Get geographic regions where this languoid is spoken."""
        return self.get_related(RelationType.SPOKEN_IN_REGION, GeographicRegion)

    @property
    def country_codes(self) -> list[str]:
        """Get country codes derived from SPOKEN_IN_REGION relations."""
        return [r.country_code for r in self.regions if r.country_code]

    @property
    def official_in_countries(self) -> list[str]:
        """Get country codes where this languoid has official status (from relation metadata)."""
        official = []
        for rel in self._relations.get(RelationType.SPOKEN_IN_REGION, []):
            if rel.metadata.get("is_official"):
                region = self._store.get(rel.target_id)
                if region and isinstance(region, GeographicRegion) and region.country_code:
                    official.append(region.country_code)
        return official

    def name_in(self, language: "Languoid | str") -> str | None:
        """Get the name of this languoid in another language.

        Args:
            language: A Languoid object or BCP-47 code string

        Examples:
            dutch.name_in(french)   # "néerlandais"
            dutch.name_in("fr")     # "néerlandais"
        """
        if not isinstance(self._store, DataStore) or self._store.name_cache is None:
            return None

        if isinstance(language, Languoid):
            locale = language.id  # canonical ID
        else:
            locale = language  # BCP-47 code or canonical ID

        return self._store.name_cache.get_name_in(self.id, locale)

    def nllb_codes(self, use_bcp_47: bool = False) -> list[str]:
        """Get NLLB-style language-script codes (e.g., 'nld_Latn').

        Args:
            use_bcp_47: If True, use BCP-47 code instead of ISO 639-3
        """
        base = self.bcp_47 if use_bcp_47 else (self.iso_639_3 or self.bcp_47)
        if base is None:
            return []
        return [f"{base}_{s.iso_15924}" for s in self.scripts if s.iso_15924]

    @property
    def languoids_with_same_script(self) -> list["Languoid"]:
        """Find other languoids that share any script with this one."""
        result = set()
        for script in self.scripts:
            result.update(script.languoids)
        result.discard(self)
        return list(result)

    @property
    def languoids_in_same_region(self) -> list["Languoid"]:
        """Find other languoids spoken in the same regions."""
        result = set()
        for region in self.regions:
            result.update(region.languoids)
        result.discard(self)
        return list(result)

    def descendants(self, max_depth: int | None = None) -> list["Languoid"]:
        """Get all descendants (recursive through children), can be limited to max_depth."""
        result: list["Languoid"] = []

        def collect(lang: "Languoid", depth: int = 0) -> None:
            if max_depth and depth >= max_depth:
                return
            for child in lang.children:
                result.append(child)
                collect(child, depth + 1)

        collect(self)
        return result

    @property
    def descendant_scripts(self) -> list["Script"]:
        """Get all scripts used by this languoid and its descendants."""
        scripts = set(self.scripts)
        for desc in self.descendants():
            scripts.update(desc.scripts)
        return list(scripts)

    def __repr__(self) -> str:
        return f"Languoid(({self.__dict__!r})"


class Script(TraversableEntity):
    """Writing system entity"""

    def __init__(
        self,
        entity_id: str,
        data_store: EntityContainer,
        iso_15924: str | None = None,
        name: str | None = None,
        full_name: str | None = None,
        is_historical: bool = False,
    ) -> None:
        super().__init__(entity_id, data_store)
        self.iso_15924: str | None = iso_15924
        self.name: str | None = name
        self.full_name: str | None = full_name
        self.is_historical: bool = is_historical

    # TODO: add some multi hop queries to this, maybe script -> languoid -> region "all regions that use this script?"
    @property
    def languoids(self) -> list[Languoid]:
        """Get all languoids that use this script."""
        return self.get_related(RelationType.USED_BY_LANGUOID, Languoid)

    @property
    def canonical_languoids(self) -> list[Languoid]:
        """Get languoids where this is the canonical/primary script."""
        return [lang for lang in self.languoids if self.is_canonical_for(lang)]

    def is_canonical_for(self, languoid: Languoid) -> bool:
        """Check if this script is canonical for a given languoid."""
        relations = self._relations.get(RelationType.USED_BY_LANGUOID, [])
        for rel in relations:
            if rel.target_id == languoid.id:
                return rel.metadata.get("is_canonical", False)
        return False

    @property
    def languoid_count(self) -> int:
        """Get count of languoids using this script (without loading all entities)."""
        return len(self._relations.get(RelationType.USED_BY_LANGUOID, []))

    def __repr__(self) -> str:
        return f"Script({self.name or self.id}, code={self.iso_15924})"


class GeographicRegion(TraversableEntity):
    """Geographic region/area"""

    def __init__(
        self,
        entity_id: str,
        data_store: EntityContainer,
        name: str | None = None,
        country_code: str | None = None,
        # ISO 3166-1 additional fields
        official_name: str | None = None,
        # ISO 3166-2 subdivisions
        subdivision_code: str | None = None,
        subdivision_type: str | None = None,
        parent_country_code: str | None = None,
        # ISO 3166-3 historical countries
        is_historical: bool = False,
    ) -> None:
        super().__init__(entity_id, data_store)
        self.name: str | None = name
        self.country_code: str | None = country_code

        # ISO 3166-1 additional fields (from pycountry)
        self.official_name: str | None = official_name

        # ISO 3166-2 subdivisions (states, provinces)
        self.subdivision_code: str | None = subdivision_code
        self.subdivision_type: str | None = subdivision_type
        self.parent_country_code: str | None = parent_country_code

        # ISO 3166-3 historical countries
        self.is_historical: bool = is_historical

    @property
    def direct_languoids(self) -> list[Languoid]:
        """Get languoids directly associated with this region (non-transitive)."""
        return self.get_related(RelationType.LANGUOIDS_IN_REGION, Languoid)

    # TODO: going from region to region should probably follow the parent-child idea of Languoid as well
    @property
    def languoids(self) -> list[Languoid]:
        """Get all languoids in this region and its child regions (transitive)."""
        langs = set(self.direct_languoids)
        for child in self.child_regions:
            langs.update(child.languoids)
        for sub in self.subdivisions:
            langs.update(sub.direct_languoids)
        return list(langs)

    @property
    def child_regions(self) -> list["GeographicRegion"]:
        """Get child regions (via HAS_CHILD_REGION relation)."""
        return self.get_related(RelationType.HAS_CHILD_REGION, GeographicRegion)

    @property
    def parent_region(self) -> "GeographicRegion | None":
        """Get parent region (for subdivisions -> country, or hierarchy)"""
        parents = self.get_related(RelationType.IS_PART_OF, GeographicRegion)
        return parents[0] if parents else None

    @property
    def subdivisions(self) -> list["GeographicRegion"]:
        """Get all subdivisions of this region (for countries -> states/provinces)"""
        if not self.country_code or not isinstance(self._store, DataStore):
            return []
        return self._store.query(GeographicRegion, parent_country_code=self.country_code)

    def __repr__(self) -> str:
        return f"GeographicRegion({self.name or self.id})"
