import csv
import json
import logging
from pathlib import Path
from typing import Any

from qq.data_model import (
    CanonicalId,
    DataSource,
    DeprecatedCode,
    EndangermentStatus,
    IdType,
    LanguageScope,
    NameEntry,
    RelationType,
)
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid

logger = logging.getLogger(__name__)


class LinguaMetaImporter(BaseImporter):
    """Import data from LinguaMeta JSON files and overview TSV file"""

    source = DataSource.LINGUAMETA

    def __init__(self, resolver):
        super().__init__(resolver)
        self._endangerment_by_code: dict[str, str] = {}
        self._name_data: dict[CanonicalId, list[NameEntry]] = {}

    @property
    def name_data(self) -> dict[CanonicalId, list[NameEntry]]:
        """Name data collected during import, keyed by canonical entity ID."""
        return self._name_data

    def import_data(self, data_path: Path) -> None:
        """Import from LinguaMeta directory structure"""
        languages_dir = data_path / "data"

        # The TSV is an overview file with some info that's not in the individual language files
        tsv_path = data_path / "linguameta.tsv"
        self._load_endangerment_status(tsv_path)

        logger.info("Importing locales and scripts...")

        # These are separate files with just locales and scripts
        locales_file = languages_dir / "locales.json"
        scripts_file = languages_dir / "scripts.json"

        self._import_locales(locales_file)
        self._import_scripts(scripts_file)

        # The per-language files
        special_files = {"locales", "scripts"}
        json_files = [p for p in languages_dir.glob("*.json") if len(p.stem) in (2, 3) and p.stem not in special_files]
        logger.info(f"Found {len(json_files)} LinguaMeta language files")

        for json_file in json_files:
            with open(json_file, "r", encoding="utf-8") as f:
                lang_data = json.load(f)
            self._import_language(lang_data)

        self.log_stats()

    def _import_language(self, data: dict[str, Any]) -> None:
        """Import a single language from LinguaMeta format"""

        # Build identifier dict with all available IDs
        identifiers = {}

        if data.get("bcp_47_code"):
            identifiers[IdType.BCP_47] = data["bcp_47_code"]
        if data.get("iso_639_3_code"):
            identifiers[IdType.ISO_639_3] = data["iso_639_3_code"]
        if data.get("iso_639_2b_code"):
            identifiers[IdType.ISO_639_2B] = data["iso_639_2b_code"]
        if data.get("glottocode"):
            identifiers[IdType.GLOTTOCODE] = data["glottocode"]
        if data.get("wikidata_id"):
            identifiers[IdType.WIKIDATA_ID] = data["wikidata_id"]

        if not identifiers:
            logger.warning(f"No identifiers found for language: {data}")
            return

        if not (name := self._extract_name(data)):
            raise ValueError("No language data found! This should not be possible.")
        endonym = self._extract_endonym(data)
        speaker_count = self._parse_speaker_count(data)

        # Extract ISO 639-3 scope from language_scope data
        scope: LanguageScope | None = None
        if scope_data := data.get("language_scope"):
            if scope_str := scope_data.get("scope"):
                scope_map = {
                    "LANGUAGE": LanguageScope.INDIVIDUAL,
                    "MACROLANGUAGE": LanguageScope.MACROLANGUAGE,
                    "SPECIAL": LanguageScope.SPECIAL,
                    "I": LanguageScope.INDIVIDUAL,
                    "M": LanguageScope.MACROLANGUAGE,
                    "S": LanguageScope.SPECIAL,
                }
                scope = scope_map.get(scope_str.upper())

        # Create or update languoid using the resolver (basic attributes first)
        languoid = self.get_or_create_languoid(identifiers)

        # Set fields directly
        if name:
            languoid.name = name
        if endonym:
            languoid.endonym = endonym
        if speaker_count:
            languoid.speaker_count = speaker_count
        if scope:
            languoid.scope = scope

        # Store name_data separately (not on entity)
        if "name_data" in data:
            self._name_data[languoid.id] = [
                NameEntry(
                    name=e["name"],
                    bcp_47_code=e.get("bcp_47_code"),
                    is_canonical=e.get("is_canonical"),
                )
                for e in data["name_data"]
                if e.get("name")
            ]
        # Store language description
        if desc := data.get("language_description"):
            if description_text := desc.get("description"):
                languoid.description = description_text

        # Set endangerment status from TSV lookup
        bcp47 = data.get("bcp_47_code")
        if bcp47 and bcp47 in self._endangerment_by_code:
            raw_status = self._endangerment_by_code[bcp47]
            try:
                languoid.endangerment_status = EndangermentStatus(raw_status)
            except ValueError:
                logger.warning(f"Unknown endangerment status '{raw_status}' for {bcp47}")

        # Import regions/countries from language_script_locale with relation metadata
        if lsl := data.get("language_script_locale"):
            self._import_regions_with_metadata(languoid, lsl)

        # Import scripts from language_script_locale
        scripts = self._extract_scripts(data)
        if scripts:
            self._import_scripts_basic(languoid, scripts)

        # Import deprecated BCP-47 code
        if deprecated_bcp47 := data.get("deprecated_bcp_47_code"):
            dc = DeprecatedCode(
                code=deprecated_bcp47,
                code_type=IdType.BCP_47,
            )
            if languoid.deprecated_codes is None:
                languoid.deprecated_codes = []
            languoid.deprecated_codes.append(dc)

            # Register in resolver: old code -> this languoid, and mark as deprecated
            self.resolver.register_alias(IdType.BCP_47, deprecated_bcp47, languoid.id)
            self.resolver.register_deprecated(IdType.BCP_47, deprecated_bcp47, "Deprecated BCP-47 code")

    def _load_endangerment_status(self, tsv_path: Path) -> None:
        """Load endangerment status from linguameta.tsv into a BCP-47 lookup."""
        with open(tsv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                code = row.get("bcp_47_code", "").strip()
                status = row.get("endangerment_status", "").strip()
                if code and status:
                    self._endangerment_by_code[code] = status
        logger.info(f"Loaded endangerment status for {len(self._endangerment_by_code)} languages from TSV")

    def _extract_name(self, data: dict[str, Any]) -> str | None:
        """Extract the canonical name for the language (preferring English canonical name)"""
        name_data = data.get("name_data", [])

        canonical_any: str | None = None
        english_any: str | None = None
        first: str | None = None

        for entry in name_data:
            name = entry.get("name")
            if not name:
                continue
            if first is None:
                first = name
            is_canonical = entry.get("is_canonical")
            is_english = entry.get("bcp_47_code") == "en"
            if is_canonical and is_english:
                return name  # best possible match, exit early
            if is_canonical and canonical_any is None:
                canonical_any = name
            if is_english and english_any is None:
                english_any = name

        return canonical_any or english_any or first

    def _extract_endonym(self, data: dict[str, Any]) -> str | None:
        """Extract the endonym (name in the language itself)"""
        name_data = data.get("name_data", [])
        bcp_47_code = data.get("bcp_47_code")

        if not bcp_47_code:
            return None

        # Look for canonical name where the bcp_47_code matches the language being described
        canonical_match = None
        first_match = None

        for entry in name_data:
            if entry.get("bcp_47_code") == bcp_47_code:
                name = entry.get("name")
                if not first_match:
                    first_match = name
                if entry.get("is_canonical"):
                    canonical_match = name
                    break

        return canonical_match or first_match

    def _unpack_language_script_locale(self, lsl: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Unpack language_script_locale into directly accessible attributes.

        Returns dict with:
        - country_codes: list of unique country codes
        - official_in_countries: list of countries where language is official
        - speaker_count_by_country: dict mapping country code to speaker count
        """
        country_codes: set[str] = set()
        official_in: set[str] = set()
        speaker_counts: dict[str, int] = {}

        # TODO: not sure if this is entirely correct
        #       maybe keep the LinguaMeta structure?
        for entry in lsl:
            locale = entry.get("locale", {})
            code = locale.get("iso_3166_code", "").upper()
            if not code:
                continue

            country_codes.add(code)

            # Check official status
            official = entry.get("official_status", {})
            if official.get("has_official_status"):
                official_in.add(code)

            # Aggregate speaker counts
            speaker_data = entry.get("speaker_data", {})
            num_speakers = speaker_data.get("number_of_speakers")
            if isinstance(num_speakers, int):
                speaker_counts[code] = speaker_counts.get(code, 0) + num_speakers

        return {
            "country_codes": sorted(country_codes),
            "official_in_countries": sorted(official_in),
            "speaker_count_by_country": speaker_counts,
        }

    def _parse_speaker_count(self, data: dict[str, Any]) -> int | None:
        """Parse speaker count from the language data"""
        # First try total_population
        if total_pop := data.get("total_population"):
            if isinstance(total_pop, int):
                return total_pop

        # Then try language_script_locale speaker_data
        for locale_data in data.get("language_script_locale", []):
            if speaker_data := locale_data.get("speaker_data"):
                if num_speakers := speaker_data.get("number_of_speakers"):
                    if isinstance(num_speakers, int):
                        return num_speakers

        return None

    def _extract_locales(self, data: dict[str, Any]) -> list[str]:
        """Extract locale/country codes from language_script_locale"""
        locales = set()
        for locale_data in data.get("language_script_locale", []):
            if locale_info := locale_data.get("locale"):
                if code := locale_info.get("iso_3166_code"):
                    locales.add(code.upper())
        return list(locales)

    def _extract_scripts(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract script information from language_script_locale.

        Returns list of dicts with script code and metadata (is_canonical, source).
        Filters out invalid placeholders ("xxxx") and Braille script ("brai").
        """
        scripts_map = {}  # Use dict to deduplicate by code while preserving metadata
        for locale_data in data.get("language_script_locale", []):
            if script_info := locale_data.get("script"):
                code = script_info.get("iso_15924_code", "").lower()

                # Skip invalid placeholders and Braille
                if not code or code == "xxxx" or code == "brai":
                    continue

                # Store the most canonical version (prefer is_canonical=true)
                is_canonical = script_info.get("is_canonical", False)
                source = script_info.get("source", "LINGUAMETA")

                if code not in scripts_map or (is_canonical and not scripts_map[code]["is_canonical"]):
                    scripts_map[code] = {
                        "code": code,
                        "is_canonical": is_canonical,
                        "source": source,
                    }

        return list(scripts_map.values())

    def _import_regions_with_metadata(self, languoid: Languoid, lsl: list[dict[str, Any]]) -> None:
        """Import geographic regions from language_script_locale with relation metadata."""
        seen_codes: set[str] = set()
        for entry in lsl:
            locale = entry.get("locale", {})
            code = locale.get("iso_3166_code", "").upper()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)

            region_id = f"region:{code.lower()}"
            region = self.get_or_create_region(region_id)
            region.country_code = code

            # Extract metadata for relation
            is_official = bool(entry.get("official_status", {}).get("has_official_status"))

            speaker_count = None
            num_speakers = entry.get("speaker_data", {}).get("number_of_speakers")
            if isinstance(num_speakers, int):
                speaker_count = num_speakers

            metadata: dict[str, Any] = {"is_official": is_official}
            if speaker_count is not None:
                metadata["speaker_count"] = speaker_count

            self.add_bidirectional_relation(
                languoid,
                RelationType.SPOKEN_IN_REGION,
                region,
                RelationType.LANGUOIDS_IN_REGION,
                **metadata,
            )

    def _import_scripts_basic(self, languoid: Languoid, scripts_data: list[dict[str, Any]]) -> None:
        """
        Import script information with canonicality metadata.

        Args:
            languoid: The languoid entity to attach scripts to
            scripts_data: List of dicts with keys: code, is_canonical, source
        """
        for script_info in scripts_data:
            script_code = script_info["code"]
            is_canonical = script_info.get("is_canonical", False)

            script_id = f"script:{script_code.lower()}"
            script = self.get_or_create_script(script_id)
            script.iso_15924 = script_code.capitalize()

            self.add_bidirectional_relation(
                languoid,
                RelationType.USES_SCRIPT,
                script,
                RelationType.USED_BY_LANGUOID,
                is_canonical=is_canonical,
            )

    def _import_locales(self, locales_file: Path) -> None:
        """Import locale/region data from locales.json"""
        with open(locales_file, "r", encoding="utf-8") as f:
            locales_data = json.load(f)

        locale_map = locales_data.get("locale_map", [])
        logger.info(f"Importing {len(locale_map)} locales...")

        for locale_entry in locale_map:
            locale_info = locale_entry.get("locale", {})
            locale_code = locale_info.get("locale_code")
            locale_name = locale_info.get("locale_name")

            if not locale_code:
                continue

            region_id = f"region:{locale_code.lower()}"
            region = self.get_or_create_region(region_id)
            region.country_code = locale_code
            region.name = locale_name
            self.stats.entities_created += 1

        logger.info(f"Imported {len(locale_map)} locales")

    def _import_scripts(self, scripts_file: Path) -> None:
        """
        Import script data from scripts.json.

        Filters out invalid placeholders ("xxxx") and Braille ("brai") script.
        """
        with open(scripts_file, "r", encoding="utf-8") as f:
            scripts_data = json.load(f)

        script_map = scripts_data.get("script_map", [])
        logger.info(f"Importing {len(script_map)} scripts...")

        imported_count = 0
        for script_entry in script_map:
            script_info = script_entry.get("script", {})
            script_code = script_info.get("name", "").lower()
            full_name = script_info.get("full_name")

            if not script_code or script_code == "xxxx" or script_code == "brai":
                continue

            script_id = f"script:{script_code.lower()}"
            script = self.get_or_create_script(script_id)
            script.iso_15924 = script_code.capitalize()
            script.name = full_name
            imported_count += 1

        logger.info(f"Imported {imported_count} scripts (filtered out invalid/Braille)")
