import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from qq.data_model import (
    CanonicalId,
    DataSource,
    IdType,
    LanguageScope,
    LanguageStatus,
    LanguoidLevel,
    NameEntry,
    RelationType,
)
from qq.importers.base_importer import BaseImporter
from qq.interface import GeographicRegion

logger = logging.getLogger(__name__)


class PycountryImporter(BaseImporter):
    """
    Enrich region/country data and languoid metadata using pycountry JSON data files.

    Imports data from:
    - ISO 3166-1 (countries)
    - ISO 3166-2 (country subdivisions)
    - ISO 3166-3 (historical countries)
    - ISO 639-3  (individual language codes -> scope, status, ISO 639-1 aliases)
    - ISO 639-5  (language family codes)
    - ISO 15924  (script codes)
    """

    source = DataSource.PYCOUNTRY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._countries_data: dict[str, Any] = {}
        self._subdivisions_data: dict[str, list[dict[str, Any]]] = {}
        self._historical_data: dict[str, Any] = {}
        self._languages_data: dict[str, Any] = {}
        self._families_data: dict[str, Any] = {}
        self._scripts_data: dict[str, Any] = {}
        self._name_data: dict[CanonicalId, list[NameEntry]] = {}

    @property
    def name_data(self) -> dict[CanonicalId, list[NameEntry]]:
        """Access collected name data keyed by canonical ID."""
        return self._name_data

    def import_data(self, data_path: Path) -> None:
        if not data_path or not data_path.exists():
            raise FileNotFoundError(f"Pycountry data path not found: {data_path}")

        logger.info("Loading pycountry data from all ISO standards")

        self._load_countries(data_path / "iso3166-1.json")
        self._load_subdivisions(data_path / "iso3166-2.json")
        self._load_historical_countries(data_path / "iso3166-3.json")
        self._load_languages(data_path / "iso639-3.json")
        self._load_families(data_path / "iso639-5.json")
        self._load_scripts(data_path / "iso15924.json")

        logger.info("Creating/enriching entities from pycountry data")
        self._import_regions()
        self._import_languoids()
        self._import_scripts()
        self._create_missing_languoids()
        self._create_family_languoids()

        self.log_stats()

    def _load_json_indexed(self, path: Path, json_key: str, index_field: str, label: str) -> dict[str, Any]:
        """Load JSON file and index by a field."""

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get(json_key, [])
            indexed = {item[index_field]: item for item in items if index_field in item}
            logger.info(f"Loaded {len(indexed)} {label.lower()}")
            return indexed

    def _load_countries(self, path: Path) -> None:
        self._countries_data = self._load_json_indexed(path, "3166-1", "alpha_2", "ISO 3166-1 (countries)")

    def _load_subdivisions(self, path: Path) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            subdivisions_list = data.get("3166-2", [])

            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for subdivision in subdivisions_list:
                code = subdivision.get("code", "")
                if "-" in code:
                    country_code = code.split("-")[0]
                    grouped[country_code].append(subdivision)

            self._subdivisions_data = dict(grouped)
            logger.info(f"Loaded {len(subdivisions_list)} subdivisions from {len(grouped)} countries")

    def _load_historical_countries(self, path: Path) -> None:
        self._historical_data = self._load_json_indexed(path, "3166-3", "alpha_2", "ISO 3166-3 (historical)")

    def _load_languages(self, path: Path) -> None:
        self._languages_data = self._load_json_indexed(path, "639-3", "alpha_3", "ISO 639-3 (languages)")

    def _load_families(self, path: Path) -> None:
        self._families_data = self._load_json_indexed(path, "639-5", "alpha_3", "ISO 639-5 (families)")

    def _load_scripts(self, path: Path) -> None:
        self._scripts_data = self._load_json_indexed(path, "15924", "alpha_4", "ISO 15924 (scripts)")

    def _import_regions(self) -> None:
        """Create region entities from ISO 3166-1 countries."""
        logger.info(f"Importing {len(self._countries_data)} countries")

        for country_code_upper, country in self._countries_data.items():
            region_id = f"region:{country_code_upper.lower()}"
            region = self.get_or_create_region(region_id)
            region.country_code = country_code_upper

            if name := country.get("name"):
                region.name = self._clean_name(name)
            if official_name := country.get("official_name"):
                region.official_name = self._clean_name(official_name)

        # Historical countries
        for country_code_upper, historical in self._historical_data.items():
            region_id = f"region:{country_code_upper.lower()}"
            region = self.get_or_create_region(region_id)
            region.country_code = country_code_upper
            region.is_historical = True
            if not region.name:
                if name := historical.get("name"):
                    region.name = self._clean_name(name)

        # Subdivisions
        for country_code_upper, subdivisions in self._subdivisions_data.items():
            for subdivision_data in subdivisions:
                self._create_subdivision(subdivision_data, country_code_upper)

    def _create_subdivision(self, data: dict[str, Any], parent_country_code: str) -> None:
        """Create a subdivision entity with IS_PART_OF relation to parent country."""
        subdivision_code = data.get("code")
        if not subdivision_code:
            return

        region_id = f"region:{subdivision_code.lower()}"
        region = self.get_or_create_region(region_id)
        region.subdivision_code = subdivision_code
        region.subdivision_type = data.get("type")  # TODO: enum?
        region.parent_country_code = parent_country_code

        if name := data.get("name"):
            if not region.name:
                region.name = self._clean_name(name)

        # Link subdivision to parent country
        # TODO: this should be completely transitive (from World you can get to all regions)
        parent_id = f"region:{parent_country_code.lower()}"
        parent = self.entity_set.get(parent_id)
        if parent and isinstance(parent, GeographicRegion):
            self.add_bidirectional_relation(
                region,
                RelationType.IS_PART_OF,
                parent,
                RelationType.HAS_CHILD_REGION,
            )

    def _import_languoids(self) -> None:
        """Enrich existing languoids with ISO 639-3 scope, status, and ISO 639-1 aliases."""
        enriched_count = 0
        iso639_1_count = 0

        for alpha_3, lang_data in self._languages_data.items():
            canonical_id = self.resolver.resolve(IdType.ISO_639_3, alpha_3)
            if not canonical_id:
                continue  # Will be handled by _create_missing_languoids

            languoid = self.resolve_languoid(IdType.ISO_639_3, alpha_3)
            if not languoid:
                continue

            if name := lang_data.get("name"):
                self._name_data[languoid.id] = [
                    # "en" is a valid BCP-47 code; resolve_locale_codes() in build_database.py
                    # converts it to the canonical ID for English before saving.
                    NameEntry(name=name, bcp_47_code="en", is_canonical=True)
                ]
            if scope := lang_data.get("scope"):
                languoid.scope = LanguageScope(scope)
            if iso_type := lang_data.get("type"):
                languoid.status = LanguageStatus(iso_type)
            # ISO 639-2T codes are identical to ISO 639-3 alpha_3 codes
            # TODO: maybe this is too aggressive since it's a subset?
            #       probably better to import this directly
            self.resolver.register_alias(IdType.ISO_639_2T, alpha_3, canonical_id)
            if alpha_2 := lang_data.get("alpha_2"):
                languoid.iso_639_1 = alpha_2
                self.resolver.register_alias(IdType.ISO_639_1, alpha_2, canonical_id)
                if not self.resolver.resolve(IdType.BCP_47, alpha_2):
                    self.resolver.register_alias(IdType.BCP_47, alpha_2, canonical_id)
                iso639_1_count += 1
            enriched_count += 1

        logger.info(f"Enriched {enriched_count} languoids with ISO 639-3 data")
        logger.info(f"Registered {iso639_1_count} ISO 639-1 aliases")
        self.stats.entities_updated += enriched_count

    def _create_missing_languoids(self) -> None:
        """Create languoid entities for ISO 639-3 codes not yet in qq."""
        created = 0
        for alpha_3, lang_data in self._languages_data.items():
            if self.resolver.resolve(IdType.ISO_639_3, alpha_3):
                continue

            identifiers = {IdType.ISO_639_3: alpha_3}
            languoid = self.get_or_create_languoid(identifiers)
            languoid.name = lang_data.get("name")

            if name := lang_data.get("name"):
                # see above
                self._name_data[languoid.id] = [NameEntry(name=name, bcp_47_code="en", is_canonical=True)]

            # ISO 639-2T codes are identical to ISO 639-3 alpha_3 codes
            self.resolver.register_alias(IdType.ISO_639_2T, alpha_3, languoid.id)
            if alpha_2 := lang_data.get("alpha_2"):
                languoid.iso_639_1 = alpha_2
                self.resolver.register_alias(IdType.ISO_639_1, alpha_2, languoid.id)
                if not self.resolver.resolve(IdType.BCP_47, alpha_2):
                    self.resolver.register_alias(IdType.BCP_47, alpha_2, languoid.id)

            if scope := lang_data.get("scope"):
                languoid.scope = LanguageScope(scope)
            if iso_type := lang_data.get("type"):
                languoid.status = LanguageStatus(iso_type)
            created += 1

        logger.info(f"Created {created} languoids from ISO 639-3 codes not in other sources")

    def _create_family_languoids(self) -> None:
        """Create family-level languoid entities from ISO 639-5."""
        created = 0
        for alpha_3, family_data in self._families_data.items():
            if self.resolver.resolve(IdType.ISO_639_5, alpha_3):
                continue
            if self.resolver.resolve(IdType.ISO_639_3, alpha_3):
                continue

            identifiers = {IdType.ISO_639_5: alpha_3}
            languoid = self.get_or_create_languoid(identifiers)
            name = self._clean_name(family_data.get("name")) if family_data.get("name") else None
            languoid.name = name
            languoid.level = LanguoidLevel.FAMILY

            if name:
                # see above
                self._name_data[languoid.id] = [NameEntry(name=name, bcp_47_code="en", is_canonical=True)]

            created += 1

        logger.info(f"Created {created} family languoids from ISO 639-5")

    def _import_scripts(self) -> None:
        """Enrich scripts with ISO 15924 data."""
        enriched_count = 0

        for alpha_4, script_data in self._scripts_data.items():
            script_id = f"script:{alpha_4.lower()}"
            script = self.get_or_create_script(script_id)
            script.iso_15924 = alpha_4

            if name := script_data.get("name"):
                script.full_name = self._clean_name(name)
                if not script.name:
                    script.name = self._clean_name(name)
            enriched_count += 1

        logger.info(f"Imported/enriched {enriched_count} scripts with ISO 15924 data")
        self.stats.entities_updated += enriched_count

    @staticmethod
    def _clean_name(name: str) -> str:
        """Remove extra things in parentheses that pycountry uses for alternative names."""
        # TODO: also import these as alternative names for countries / regions?
        return name.split("(")[0].strip()
