import csv
import html
import logging
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from qq.data_model import DataSource, IdType
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid

logger = logging.getLogger(__name__)

NameIndex = dict[str, set[str]]
WalsIdentifiers = tuple[str, str]
WalsNameIndex = dict[str, list[WalsIdentifiers]]
WalsNameIndexes = tuple[WalsNameIndex, WalsNameIndex]


class JoshiImporter(BaseImporter):
    """Import the language resource classes (0-5) from Joshi et al. (2020).

    The classes are based on language names, which are tricky to match.
    We use an export from WALS from around the time of the paper to get the names.
    Others are matched through Wikipedia or Glottolog, or with a small fallback set.
    """

    source = DataSource.JOSHI

    # Edition names used by Joshi that differ from the current Wikistats names.
    _HISTORICAL_WIKIPEDIA_CODES = {
        "bhojpuri": "bh",
        "buryat": "bxr",
        "chavacano": "cbk-zam",
        "eastern punjabi": "pa",
        "franco provencal": "frp",
        "ilocano": "ilo",
        "jamaican patois": "jam",
        "kabardian": "kbd",
        "konkani": "gom",
        "kurdish kurmanji": "ku",
        "kurdish sorani": "ckb",
        "lingua franca nova": "lfn",
        "newar": "new",
        "odia": "or",
        "southern azerbaijani": "azb",
        "waray": "war",
        "western punjabi": "pnb",
    }

    def __init__(
        self,
        *args,
        glottolog_data_path: Path,
        wals_data_path: Path | None = None,
        wikipedia_data_path: Path | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.glottolog_data_path = glottolog_data_path
        self.wals_data_path = wals_data_path
        self.wikipedia_data_path = wikipedia_data_path

    def import_data(self, data_path: Path) -> None:
        ratings_file = data_path / "lang2tax.txt"
        primary_names, alternative_names, levels = self._load_glottolog_name_indexes()
        wals_names = self._load_wals_name_indexes()
        wikipedia_names = self._load_wikipedia_name_index()
        ratings = self._load_ratings(ratings_file)

        matched_rows = 0
        source_conflicts = 0
        unmatched = 0
        matches_by_languoid: dict[str, list[tuple[str, int, Languoid]]] = defaultdict(list)
        for language_name, values in ratings.items():
            if len(values) != 1:
                source_conflicts += 1
                logger.warning("Conflicting Joshi ratings for %r: %s", language_name, sorted(values))
                continue

            rating = next(iter(values))
            languoid = self._resolve_language(
                language_name,
                rating,
                wals_names,
                wikipedia_names,
                primary_names,
                alternative_names,
                levels,
            )
            if languoid is None:
                unmatched += 1
                continue
            matches_by_languoid[languoid.id].append((language_name, rating, languoid))
            matched_rows += 1

        imported = 0
        duplicate_rows = 0
        target_conflicts = 0
        for matches in matches_by_languoid.values():
            duplicate_rows += len(matches) - 1
            target_ratings = {rating for _, rating, _ in matches}
            if len(target_ratings) != 1:
                target_conflicts += 1
                logger.warning(
                    "Conflicting Joshi ratings resolve to languoid %s; using highest: %s",
                    matches[0][2].id,
                    [(name, rating) for name, rating, _ in matches],
                )

            # The source combines WALS zeroes with positive Wikipedia ratings,
            # so aliases for one language should retain the higher resource class.
            matches[0][2].joshi_rating = max(target_ratings)
            imported += 1

        logger.info(
            "Imported %d unique Joshi ratings from %d matched rows "
            "(%d duplicate rows, %d source conflicts, %d target conflicts, %d unmatched)",
            imported,
            matched_rows,
            duplicate_rows,
            source_conflicts,
            target_conflicts,
            unmatched,
        )
        self.log_stats()

    def _resolve_language(
        self,
        name: str,
        rating: int,
        wals_names: WalsNameIndexes,
        wikipedia_names: NameIndex,
        primary_names: NameIndex,
        alternative_names: NameIndex,
        levels: dict[str, str],
    ) -> Languoid | None:
        normalized = self._normalize_name(name)

        if rating > 0:
            wikipedia_match = self._resolve_wikipedia_name(normalized, wikipedia_names)
            if wikipedia_match is not None:
                return wikipedia_match

        wals_match = self._resolve_wals_name(normalized, wals_names)
        if wals_match is not None:
            return wals_match

        primary_matches = primary_names.get(normalized, set())
        alternative_matches = alternative_names.get(normalized, set())
        glottocode = self._select_glottocode(primary_matches, alternative_matches, levels)
        if glottocode is None:
            return None

        return self.resolve_languoid(IdType.GLOTTOCODE, glottocode)

    def _resolve_wikipedia_name(
        self,
        normalized_name: str,
        wikipedia_names: NameIndex,
    ) -> Languoid | None:
        codes = wikipedia_names.get(normalized_name, set())
        if not codes and (code := self._HISTORICAL_WIKIPEDIA_CODES.get(normalized_name)):
            codes = {code}
        if len(codes) != 1:
            return None

        code = next(iter(codes))
        for id_type in (IdType.WIKIPEDIA, IdType.BCP_47, IdType.ISO_639_1, IdType.ISO_639_3):
            if languoid := self.resolve_languoid(id_type, code):
                return languoid
        return None

    def _resolve_wals_name(
        self,
        normalized_name: str,
        wals_names: WalsNameIndexes,
    ) -> Languoid | None:
        exact_names, base_names = wals_names
        candidates = exact_names.get(normalized_name, [])
        if not candidates:
            candidates = base_names.get(normalized_name, [])
        if not candidates:
            return None

        canonical_ids: set[str] = set()
        identifiers: list[tuple[IdType, str]] = []
        for glottocode, iso_code in candidates:
            for id_type, value in ((IdType.GLOTTOCODE, glottocode), (IdType.ISO_639_3, iso_code)):
                if not value:
                    continue
                canonical_id = self.resolver.resolve(id_type, value)
                if canonical_id:
                    canonical_ids.add(canonical_id)
                    identifiers.append((id_type, value))

        if len(canonical_ids) != 1:
            return None
        canonical_id = next(iter(canonical_ids))
        for id_type, value in identifiers:
            if self.resolver.resolve(id_type, value) == canonical_id:
                return self.resolve_languoid(id_type, value)
        return None

    @staticmethod
    def _select_glottocode(
        primary_matches: set[str],
        alternative_matches: set[str],
        levels: dict[str, str],
    ) -> str | None:
        """Prefer language, then dialect, then family."""
        if not primary_matches:
            return next(iter(alternative_matches)) if len(alternative_matches) == 1 else None

        candidates = primary_matches | alternative_matches
        for level in ("language", "dialect", "family"):
            matches = {glottocode for glottocode in candidates if levels.get(glottocode) == level}
            primary_at_level = matches & primary_matches
            if len(primary_at_level) == 1:
                return next(iter(primary_at_level))
            if len(matches) == 1:
                return next(iter(matches))
            if len(matches) > 1:
                break

        return next(iter(primary_matches)) if len(primary_matches) == 1 else None

    def _load_wals_name_indexes(self) -> WalsNameIndexes:
        exact_names: WalsNameIndex = defaultdict(list)
        base_names: WalsNameIndex = defaultdict(list)
        if self.wals_data_path is None:
            return {}, {}

        with open(self.wals_data_path / "languages.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get("Name", "").strip()
                if not name:
                    continue
                identifiers = (
                    row.get("Glottocode", "").strip(),
                    row.get("ISO639P3code", "").strip(),
                )
                exact_names[self._normalize_name(name)].append(identifiers)
                base_name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
                base_names[self._normalize_name(base_name)].append(identifiers)

        return dict(exact_names), dict(base_names)

    def _load_wikipedia_name_index(self) -> NameIndex:
        names: NameIndex = defaultdict(set)
        if self.wikipedia_data_path is None:
            return {}

        with open(self.wikipedia_data_path / "wikipedia.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, skipinitialspace=True):
                code = row.get("prefix", "").strip()
                name = html.unescape(row.get("lang", "")).strip()
                if code and name:
                    names[self._normalize_name(name)].add(code)
        return dict(names)

    def _load_glottolog_name_indexes(
        self,
    ) -> tuple[NameIndex, NameIndex, dict[str, str]]:
        primary_names: NameIndex = defaultdict(set)
        levels: dict[str, str] = {}
        with open(self.glottolog_data_path / "languages.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                name = row.get("Name", "").strip()
                glottocode = row.get("Glottocode", "").strip()
                if name and glottocode:
                    primary_names[self._normalize_name(name)].add(glottocode)
                    levels[glottocode] = row.get("Level", "").strip()

        alternative_names: NameIndex = defaultdict(set)
        names_file = self.glottolog_data_path / "names.csv"
        if names_file.exists():
            with open(names_file, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    name = row.get("Name", "").strip()
                    glottocode = row.get("Language_ID", "").strip()
                    if name and glottocode:
                        alternative_names[self._normalize_name(name)].add(glottocode)

        return dict(primary_names), dict(alternative_names), levels

    @staticmethod
    def _load_ratings(path: Path) -> dict[str, set[int]]:
        ratings: dict[str, set[int]] = defaultdict(set)
        with open(path, encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    name, raw_rating = line.rsplit(",", 1)
                    rating = int(raw_rating)
                except ValueError:
                    logger.warning("Invalid Joshi rating at line %d: %r", line_number, line)
                    continue
                if not 0 <= rating <= 5:
                    logger.warning("Out-of-range Joshi rating at line %d: %r", line_number, line)
                    continue
                ratings[name.strip()].add(rating)
        return dict(ratings)

    @staticmethod
    def _normalize_name(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value).casefold()
        without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
        return " ".join("".join(char if char.isalnum() else " " for char in without_marks).split())
