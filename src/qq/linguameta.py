import gzip
import json
import os
from enum import Enum
from pathlib import Path
from typing import Generator
import itertools

import numpy as np
import pandas as pd
from pydantic import AfterValidator, BaseModel, BeforeValidator
from typing_extensions import Annotated

from qq.constants import LINGUAMETA_DUMP_PATH, LinguaMetaPaths

PathLike = str | os.PathLike


# Languoid identifiers
BCP_47_CODE = str
ISO_639_3_CODE = str
ISO_639_2B_CODE = str
Glottocode = str
Wikidata_ID = str
Wikipedia_ID = str  # TODO: move elsewhere since it's not from linguameta?
# Script identifier
ISO_15924_CODE = str
# Territory identifier
ISO_3166_CODE = str
# This is a combination of ISO 693 or BCP 47 and ISO 15924 -> zho_Hans or zho_Hant for example
# Technically similar to the first parts of an IETF Tag https://en.wikipedia.org/wiki/IETF_language_tag
# but instead follows 'conventions' from NLP research, such as used in Glotscript, GlotID, NLLB, Goldfish, etc.
NLLB_STYLE_CODE_BCP_47 = str
NLLB_STYLE_CODE_ISO_639_3 = str


class LanguoidID(str, Enum):
    BCP_47_CODE = "BCP_47_CODE"
    ISO_639_3_CODE = "ISO_639_3_CODE"
    ISO_639_2B_CODE = "ISO_639_2B_CODE"
    Glottocode = "Glottocode"
    Wikidata_ID = "Wikidata_ID"
    Wikipedia_ID = "Wikipedia_ID"  # TODO: move elsewhere since it's not from linguameta?


# All ids as property names (as used in Languoid and IDMapping for example)
ALL_IDS = [lang.lower() for lang in LanguoidID._member_names_]


# For missing locales and scripts.
MISSING_PLACEHOLDER = "xxxx"
# Braille ISO 15924 script code
BRAILLE = "Brai"


def format_script_iso(value: str | None) -> str | None:
    """Convert the missing script to None for consistency and title case code since that's what ISO 15924 should be."""
    return None if (value == MISSING_PLACEHOLDER) or (value is None) else value.title()


def split_string(value: list | str | None) -> str | None:
    if not value:
        return None
    if isinstance(value, list):
        return value
    return [val.strip() for val in value.split(", ") if val]


class Scope(str, Enum):
    """The Scope of a Languoid describes what it covers."""

    LANGUAGE = "LANGUAGE"
    MACROLANGUAGE = "MACROLANGUAGE"


class Endangerment(str, Enum):
    """Endangerment status of a Languoid as classified by the UNESCO Atlas of the World's Languages."""

    SAFE = "SAFE"  # Safe; not endangered
    VULNERABLE = "VULNERABLE"  # Vulnerable
    DEFINITE = "DEFINITE"  # Definitely endangered
    SEVERE = "SEVERE"  # Severely endangered
    CRITICAL = "CRITICAL"  # Critically endangered
    EXTINCT = "EXTINCT"  # Extinct; no longer spoken by L1 speakers

    @classmethod
    def from_description(cls, desc: str):
        DESC_TO_ENUM = {
            "Not endangered": Endangerment.SAFE,
            "Vulnerable": Endangerment.VULNERABLE,
            "Definitely endangered": Endangerment.DEFINITE,
            "Severely endangered": Endangerment.SEVERE,
            "Critically endangered": Endangerment.CRITICAL,
            "Extinct": Endangerment.EXTINCT,
        }
        if desc not in DESC_TO_ENUM:
            raise ValueError(f"Unknown endangerment description: {desc}")
        return DESC_TO_ENUM[desc]


def get_endangerment(value: Endangerment | str | None) -> str | None:
    if not value:
        return None
    if isinstance(value, Endangerment):
        return value
    # TODO: handle properly
    try:
        return Endangerment[value]
    except Exception:
        return Endangerment.from_description(value)


def add_linguameta_source(value: str) -> str:
    return value if value.startswith("LINGUAMETA-") else f"LINGUAMETA-{value}"


class SourceBasedFeature(BaseModel):
    source: Annotated[str, AfterValidator(add_linguameta_source)]


class LanguageScope(SourceBasedFeature):
    scope: Scope


class EndangermentStatus(SourceBasedFeature):
    endangerment: Endangerment


class LanguageDescription(SourceBasedFeature):
    description: str


class NameData(SourceBasedFeature):
    bcp_47_code: BCP_47_CODE
    name: str | None = None
    is_canonical: bool | None = None


class Script(SourceBasedFeature):
    iso_15924_code: Annotated[ISO_15924_CODE | None, BeforeValidator(format_script_iso)] = None
    is_canonical: bool | None = None
    is_historical: bool | None = None
    is_religious: bool | None = None
    is_for_transliteration: bool | None = None
    is_for_accessibility: bool | None = None
    is_in_widespread_use: bool | None = None
    has_official_status: bool | None = None
    has_symbolic_value: bool | None = None


class SimpleLocale(SourceBasedFeature):
    iso_3166_code: ISO_3166_CODE


class SpeakerData(SourceBasedFeature):
    number_of_speakers: int


class OfficialStatus(SourceBasedFeature):
    has_official_status: bool | None = None
    has_regional_official_status: bool | None = None
    has_de_facto_official_status: bool | None = None


class Geolocation(SourceBasedFeature):
    latitude: float
    longitude: float


class LanguageScriptLocale(BaseModel):
    script: Script | None = None
    locale: SimpleLocale | None = None
    speaker_data: SpeakerData | None = None
    official_status: OfficialStatus | None = None
    geolocation: Geolocation | None = None


def to_name_dict(values: dict[BCP_47_CODE, NameData] | list[dict] | None) -> dict[BCP_47_CODE, NameData] | None:
    if not values:
        return None
    if isinstance(values, dict):
        return {k: NameData(**val) for k, val in values.items()}
    return {name.bcp_47_code: name for item in values if (name := NameData(**item))}


class Languoid(BaseModel):
    # TODO: group this more logically since this is a bit messy.
    # Possible workflow: parse languoids from all sources separately and merge when creating the graph.

    # From LinguaMeta json files
    bcp_47_code: BCP_47_CODE
    deprecated_bcp_47_code: BCP_47_CODE | None = None
    iso_639_3_code: ISO_639_3_CODE | None = None
    iso_639_2b_code: ISO_639_2B_CODE | None = None
    glottocode: Glottocode | None = None
    wikidata_id: Wikidata_ID | None = None

    # To be created from linguameta and glotscript
    nllb_style_codes_iso_639_3: list[NLLB_STYLE_CODE_ISO_639_3] | None = None
    nllb_style_codes_bcp_47: list[NLLB_STYLE_CODE_BCP_47] | None = None

    # From Wikipedia
    wikipedia_id: Wikipedia_ID | None = None
    # TODO: we might as well add all information from here: https://en.wikipedia.org/wiki/List_of_Wikipedias#Active_editions
    # From LinguaMeta json files -- continued
    total_population: int | None = None  # same as estimated_number_of_speakers in overview
    language_scope: LanguageScope | None = None
    macrolanguage_bcp_47_code: BCP_47_CODE | None = None
    individual_language_bcp_47_codes: list[BCP_47_CODE] | None = None
    endangerment_status: EndangermentStatus | None = None
    language_description: LanguageDescription | None = None
    name_data: Annotated[dict[BCP_47_CODE, NameData] | None, BeforeValidator(to_name_dict)] = None
    language_script_locale: list[LanguageScriptLocale] | None = None

    # From LinguaMeta overview tsv
    english_name: str | None = None
    endonym: str | None = None
    estimated_number_of_speakers: int | None = None
    writing_systems: Annotated[list[str] | None, BeforeValidator(split_string)] = None
    locales: Annotated[list[str] | None, BeforeValidator(split_string)] = None
    cldr_official_status: Annotated[list[str] | None, BeforeValidator(split_string)] = None
    is_macrolanguage: bool | None = None
    endangerment_status_description: Annotated[Endangerment | None, BeforeValidator(get_endangerment)] = None

    # TODO: merge endangerment_status_description and endangerment_status into one entry.
    # TODO: merge macrolanguage information
    # TODO: merge writing_systems and language_script_locale
    # TODO: allow access to name_data with an instance of a Languoid

    # TODO: add CLLD datasets here (Grambank, Wals, etc.), also see note at the top of this class.
    # For sources see:
    # - https://clld.org/datasets.html
    # - https://github.com/clld
    # - https://github.com/grambank/grambank

    @property
    def canonical_scripts(self) -> list[Script]:
        result, seen = [], set()
        # TODO: this is a messy solution, make Script hashable based on iso code?
        for lsl in self.language_script_locale:
            if lsl.script and lsl.script.is_canonical and (lsl.script.iso_15924_code not in seen):
                result.append(lsl.script)
                seen.add(lsl.script.iso_15924_code)
        return result


class LocalePopulation(SourceBasedFeature):
    population: int | None = None


class Locale(BaseModel):
    locale_code: str  # either a region code or an ISO 3166 code TODO: type properly
    locale_name: str
    locale_population: LocalePopulation | None = None


class FullLocale(BaseModel):
    locale: Locale
    region: str | None = None
    subregion: str | None = None
    regional_group: str | None = None


class IDMapping:
    def __init__(self, languoids: dict[BCP_47_CODE, Languoid]) -> None:
        # Some convenience mappings for quick access.

        all_pairs = list(itertools.permutations(ALL_IDS, 2))
        dicts = {f"{a}2{b}": dict() for a, b in all_pairs}

        for lang in languoids.values():
            for a, b in all_pairs:
                if (code_a := getattr(lang, a)) and (code_b := getattr(lang, b)):
                    dicts[f"{a}2{b}"][code_a] = code_b
                    dicts[f"{b}2{a}"][code_b] = code_a

        for key, value in dicts.items():
            setattr(self, key, value)


class LinguaMeta:
    """A class to interact with [LinguaMeta](https://aclanthology.org/2024.lrec-main.921/)."""

    def __init__(
        self,
        languoids: dict[BCP_47_CODE, Languoid],
        locales: dict[ISO_3166_CODE, FullLocale] | None = None,
    ) -> None:
        self.languoids = languoids
        self.id_mapping = IDMapping(self.languoids)
        self.locales = locales  # TODO: move locales to their own class?

    @classmethod
    def from_raw(cls, paths: LinguaMetaPaths = LinguaMetaPaths()):
        """Build the LinguaMeta content from the raw json files."""
        return cls(
            languoids={lang.bcp_47_code: lang for lang in cls._parse_languoids(paths)},
            locales={loc.locale.locale_code: loc for loc in cls._parse_locales(paths)},
        )

    @classmethod
    def from_db(cls, path: PathLike = LINGUAMETA_DUMP_PATH):
        """Build the LinguaMeta content from a previously dumped db."""
        contents = json.loads(gzip.decompress(Path(path).read_bytes()))
        return cls(
            languoids={code: Languoid(**lang) for code, lang in contents["languoids"].items()},
            locales={code: FullLocale(**loc) for code, loc in contents["locales"].items()},
        )

    def get(self, key: str, key_type: LanguoidID = LanguoidID.BCP_47_CODE) -> Languoid:
        """Get a Languoid from a given key."""

        try:
            if key_type == LanguoidID.BCP_47_CODE:
                return self.languoids[key]
            mapping_key = f"{key_type.lower()}2bcp_47_code"
            return self.languoids[getattr(self.id_mapping, mapping_key)[key]]
        except KeyError as exc:
            raise KeyError(f"Languoid for key {key} ({key_type}) not found.") from exc

    def guess(self, key: str) -> Languoid:
        """Try all known code types and get the best guess, use at your own risk!"""
        for code_name in LanguoidID.__dict__["_member_names_"]:
            try:
                return self.get(key, LanguoidID[code_name])
            except KeyError:
                pass
        raise KeyError(f"Languoid for key {key} not found for any know code type.")

    def dump(self, path: PathLike = LINGUAMETA_DUMP_PATH) -> Path:
        """Dump the contents to a gzipped json file."""

        output = {
            "languoids": {k: v.model_dump() for k, v in self.languoids.items()},
            "locales": {k: v.model_dump() for k, v in self.locales.items()},
        }

        out_file = Path(path)
        out_file.write_bytes(gzip.compress(json.dumps(output, ensure_ascii=False).encode()))
        return out_file

    @staticmethod
    def _parse_languoids(paths: LinguaMetaPaths) -> Generator[Languoid, None, None]:
        wikipedia_mapping = json.loads(Path(paths.wikipedia).read_bytes())
        wikipedia_by_iso = {value["alpha3"]: key for key, value in wikipedia_mapping.items()}

        overview_data = (
            pd.read_csv(
                paths.overview,
                sep="\t",
                index_col="bcp_47_code",
                keep_default_na=False,
            )
            .fillna(np.nan)
            .replace([np.nan, ""], [None, None])
            # The overview status is just a description, the other has source information.
            .rename(columns={"endangerment_status": "endangerment_status_description"})
            .T.to_dict()
        )

        glotscript_df = (
            pd.read_csv(
                paths.glotscript,
                sep="\t",
                index_col="ISO639-3",
                keep_default_na=False,
            )
            .fillna(np.nan)
            .replace([np.nan, ""], [None, None])
        )
        glotscript_df["ISO15924-Main"] = glotscript_df["ISO15924-Main"].str.split(", ")
        glotscript_data = glotscript_df.T.to_dict()

        for file in Path(paths.json).glob("*.json"):
            bcp_47 = file.stem
            overview = overview_data[bcp_47]
            iso_639_3 = overview.get("iso_639_3_code", None)
            wiki = {"wikipedia_id": wikipedia_by_iso.get(iso_639_3, None)}
            # TODO: this is a bit of a mess
            nllb_codes = {"nllb_style_codes_iso_639_3": None, "nllb_style_codes_bcp_47": None}

            # TODO put glotscript content into it's own pydantic classes and merge later
            # TODO provide proper source for glotscript as well
            if overview["writing_systems"]:
                # Create proper format
                original_scripts = set(overview["writing_systems"].split(", "))
                overview["writing_systems"] = sorted(list(set(original_scripts)))

                # Try to get additional writing system data
                if iso_639_3 in glotscript_data:
                    if new_scripts := glotscript_data[iso_639_3]["ISO15924-Main"]:
                        overview["writing_systems"] = sorted(list(original_scripts | set(new_scripts)))
                        # We consider glotscript as the authority when creating these nllb style codes.
                        # And we're not including Braille for the time being.
                        nllb_scripts = [scr for scr in sorted(new_scripts) if scr != BRAILLE]
                        nllb_codes["nllb_style_codes_iso_639_3"] = [f"{iso_639_3}_{scr}" for scr in nllb_scripts]
                        nllb_codes["nllb_style_codes_bcp_47"] = [f"{bcp_47}_{scr}" for scr in nllb_scripts]

            # ordering is important here
            contents = overview | json.loads(file.read_bytes()) | wiki | nllb_codes
            yield Languoid(**contents)

    @staticmethod
    def _parse_locales(paths: LinguaMetaPaths) -> Generator[FullLocale, None, None]:
        yield from (FullLocale(**content) for content in json.loads(Path(paths.locales).read_bytes())["locale_map"])
