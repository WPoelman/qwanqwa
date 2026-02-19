import csv
import logging
from pathlib import Path

from qq.data_model import CanonicalId, DataSource, IdType, NameEntry
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid, WikipediaInfo

logger = logging.getLogger(__name__)


class WikipediaImporter(BaseImporter):
    """Import Wikipedia edition data from Wikistats"""

    source = DataSource.WIKIPEDIA

    # Wikipedia language codes that don't follow standard BCP-47/ISO schemes.
    # Maps Wikipedia hyphenated code -> (IdType, standard_code) for resolution.
    _SPECIAL_CODES: dict[str, tuple[IdType, str]] = {
        "bat-smg": (IdType.ISO_639_3, "sgs"),  # Samogitian
        "be-tarask": (IdType.BCP_47, "be"),  # Belarusian (Taraškievica orthography)
        "be-x-old": (IdType.BCP_47, "be"),  # Belarusian (old orthography alias)
        "bh": (IdType.ISO_639_5, "bih"),  # Bihari languages
        "cbk-zam": (IdType.ISO_639_3, "cbk"),  # Chavacano de Zamboanga
        "fiu-vro": (IdType.ISO_639_3, "vro"),  # Võro
        "nds-nl": (IdType.ISO_639_3, "nds"),  # Dutch Low Saxon -> Low German
        "roa-rup": (IdType.ISO_639_3, "rup"),  # Aromanian
        "simple": (IdType.BCP_47, "en"),  # Simple English
        "zh-classical": (IdType.ISO_639_3, "lzh"),  # Classical Chinese
        "zh-min-nan": (IdType.ISO_639_3, "nan"),  # Min Nan Chinese
        "zh-yue": (IdType.ISO_639_3, "yue"),  # Cantonese
        "zlw-slv": (IdType.ISO_639_3, "szl"),  # Silesian
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_data: dict[CanonicalId, list[NameEntry]] = {}

    @property
    def name_data(self) -> dict[CanonicalId, list[NameEntry]]:
        """Access collected name data keyed by canonical ID."""
        return self._name_data

    def import_data(self, data_path: Path) -> None:
        """Import Wikipedia edition data from Wikistats CSV."""
        data_file = data_path / "wikipedia.csv"

        logger.info(f"Loading Wikipedia data from {data_file}")
        with open(data_file, "r", encoding="utf-8") as f:
            # skipinitialspace handles the ", " separator style in Wikistats CSV
            reader = csv.DictReader(f, skipinitialspace=True)
            for row in reader:
                self._import_wikipedia_edition(row)

        self._register_special_aliases()
        self.log_stats()

    def _import_wikipedia_edition(self, row: dict[str, str]) -> None:
        """Import one Wikipedia edition from a Wikistats CSV row."""
        wikipedia_code = row.get("prefix", "").strip()
        if not wikipedia_code:
            return

        # si_server is "//en.wikipedia.org"
        si_server = row.get("si_server", "").strip()
        if si_server.startswith("//"):
            url = f"https:{si_server}"
        else:
            url = f"https://{wikipedia_code}.wikipedia.org"

        language_name = row.get("lang", "").strip() or None
        local_name = row.get("loclang", "").strip() or None
        # "good" in Wikistats means articles (content pages meeting basic quality criteria)
        article_count = self._parse_int(row.get("good"))
        active_users = self._parse_int(row.get("activeusers"))

        languoid = self._find_languoid_for_wikipedia_code(wikipedia_code)

        if languoid:
            # Only set WikipediaInfo if not already set: prefer the primary edition
            # over variant editions (e.g. don't let "simple" overwrite "en" for English).
            if languoid.wikipedia is None:
                languoid.wikipedia = WikipediaInfo(
                    url=url,
                    code=wikipedia_code,
                    article_count=article_count,
                    active_users=active_users,
                )
            # Always register the alias so both "en" and "simple" resolve to English.
            self.resolver.register_alias(IdType.WIKIPEDIA, wikipedia_code, languoid.id)

            # Collect name data
            if language_name:
                entries: list[NameEntry] = [NameEntry(name=language_name, bcp_47_code="en", is_canonical=False)]
                if local_name and local_name != language_name:
                    entries.append(NameEntry(name=local_name, bcp_47_code=wikipedia_code, is_canonical=False))
                self._name_data[languoid.id] = entries

            self.stats.entities_updated += 1
            logger.debug(
                f"Added Wikipedia data to '{languoid.name}': "
                f"{article_count or 0:,} articles, {active_users or 0} active users"
            )
        else:
            logger.debug(f"Could not find languoid for Wikipedia code: {wikipedia_code}")

    def _register_special_aliases(self) -> None:
        """Register WIKIPEDIA aliases for compound codes without active wiki editions.

        Some historical Wikipedia codes (e.g. "bat-smg", "zh-classical") have been
        superseded by ISO 639-3 based codes ("sgs", "lzh") in Wikistats. They
        still appear in external datasets (BabelNet, etc.) and need to resolve.
        """
        for wiki_code, (id_type, std_code) in self._SPECIAL_CODES.items():
            if self.resolver.resolve(IdType.WIKIPEDIA, wiki_code):
                continue  # already registered via main import
            if languoid := self.resolve_languoid(id_type, std_code):
                self.resolver.register_alias(IdType.WIKIPEDIA, wiki_code, languoid.id)
                logger.debug(f"Registered WIKIPEDIA alias: {wiki_code} -> {languoid.id} (via {std_code})")

    def _find_languoid_for_wikipedia_code(self, wikipedia_code: str) -> Languoid | None:
        """Find languoid entity for a Wikipedia language code."""
        # Try as BCP-47 code (handles most two-letter codes like "en", "nl", "zh-Hans")
        if languoid := self.resolve_languoid(IdType.BCP_47, wikipedia_code):
            return languoid

        # Try as ISO 639-1 code
        if languoid := self.resolve_languoid(IdType.ISO_639_1, wikipedia_code):
            return languoid

        # Try as ISO 639-3 code (e.g. "ang", "got", "lzh", "tok")
        if languoid := self.resolve_languoid(IdType.ISO_639_3, wikipedia_code):
            return languoid

        # Try as ISO 639-5 code (e.g. "nah" family codes)
        if languoid := self.resolve_languoid(IdType.ISO_639_5, wikipedia_code):
            return languoid

        # Try compound/non-standard codes that have known standard equivalents
        if special := self._SPECIAL_CODES.get(wikipedia_code):
            id_type, std_code = special
            if languoid := self.resolve_languoid(id_type, std_code):
                return languoid

        logger.warning(f"Could not find Languoid for Wikipedia code {wikipedia_code}")
        return None

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        """Parse integer value safely"""
        if not value or not value.strip():
            return None
        try:
            return int(value.strip())
        except ValueError:
            logger.warning(f"Could not parse integer value: {value!r}")
            return None
