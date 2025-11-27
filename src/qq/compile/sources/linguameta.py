import json
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import AfterValidator, BaseModel, BeforeValidator
from typing_extensions import Annotated

# Languoid identifiers
BCP_47 = str
ISO_639_3 = str
ISO_639_2B = str
Glottocode = str
Wikidata_ID = str

# Script identifier
ISO_15924 = str

# Territory identifier
ISO_3166 = str

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
    bcp_47_code: BCP_47
    name: str | None = None
    is_canonical: bool | None = None


class Script(SourceBasedFeature):
    iso_15924: Annotated[ISO_15924 | None, BeforeValidator(format_script_iso)] = None
    is_canonical: bool | None = None
    is_historical: bool | None = None
    is_religious: bool | None = None
    is_for_transliteration: bool | None = None
    is_for_accessibility: bool | None = None
    is_in_widespread_use: bool | None = None
    has_official_status: bool | None = None
    has_symbolic_value: bool | None = None


class SimpleLocale(SourceBasedFeature):
    iso_3166_code: ISO_3166


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


def to_name_dict(values: dict[BCP_47, NameData] | list[dict] | None) -> dict[BCP_47, NameData] | None:
    if not values:
        return None
    if isinstance(values, dict):
        return {k: NameData(**val) for k, val in values.items()}
    return {name.bcp_47_code: name for item in values if (name := NameData(**item))}


class LinguaMetaLanguoidEntry(BaseModel):
    # From LinguaMeta json files
    bcp_47_code: BCP_47
    deprecated_bcp_47_code: BCP_47 | None = None
    iso_639_3_code: ISO_639_3 | None = None
    iso_639_2b_code: ISO_639_2B | None = None
    glottocode: Glottocode | None = None
    wikidata_id: Wikidata_ID | None = None
    total_population: int | None = None  # same as estimated_number_of_speakers in overview
    language_scope: LanguageScope | None = None
    macrolanguage_bcp_47_code: BCP_47 | None = None
    individual_language_bcp_47_codes: list[BCP_47] | None = None
    endangerment_status: EndangermentStatus | None = None
    language_description: LanguageDescription | None = None
    name_data: Annotated[dict[BCP_47, NameData] | None, BeforeValidator(to_name_dict)] = None
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


class LocalePopulation(SourceBasedFeature):
    population: int | None = None


class Locale(BaseModel):
    locale_code: str  # either a region code or an ISO 3166 code TODO: type properly
    locale_name: str
    locale_population: LocalePopulation | None = None


# From locales.json
class LinguaMetaLocaleEntry(BaseModel):
    locale: Locale
    region: str | None = None
    subregion: str | None = None
    regional_group: str | None = None


# From scripts.json
class LinguaMetaScriptEntry(BaseModel):
    # This is the ISO_15924 code, not a 'name'
    name: Annotated[ISO_15924, BeforeValidator(format_script_iso)] = None
    full_name: str  # English name


def get_linguameta_languoid_entries(overview_path: Path, json_folder_path: Path) -> list[LinguaMetaLanguoidEntry]:
    overview_data = (
        pd.read_csv(
            overview_path,
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
    entries = []
    for file in json_folder_path.glob("*.json"):
        bcp_47 = file.stem
        overview = overview_data[bcp_47]
        if overview["writing_systems"]:
            original_scripts = set(overview["writing_systems"].split(", "))
            overview["writing_systems"] = sorted(list(set(original_scripts)))

        contents = overview | json.loads(file.read_bytes())
        entries.append(LinguaMetaLanguoidEntry(**contents))

    return entries


def get_linguameta_locale_entries(path: Path) -> list[LinguaMetaLocaleEntry]:
    return [LinguaMetaLocaleEntry(**data) for data in json.loads(path.read_bytes())["locale_map"]]


def get_linguameta_script_entries(path: Path):
    return [LinguaMetaScriptEntry(**data["script"]) for data in json.loads(path.read_bytes())["script_map"]]
