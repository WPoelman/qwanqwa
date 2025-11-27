from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
DATA_DIR = PROJECT_ROOT / "data"
LOCAL_DATA_DIR = Path(__file__).parent / "data"

EXAMPLE_PATH = DOCS_DIR / "example.md"
README_PATH = PROJECT_ROOT / "README.md"

# LinguaMeta
LINGUAMETA_DUMP_PATH = LOCAL_DATA_DIR / "db.json.gz"
LINGUAMETA_JSON_PATH = DATA_DIR / "linguameta/data"
LINGUAMETA_OVERVIEW_PATH = DATA_DIR / "linguameta/linguameta.tsv"
LINGUAMETA_LOCALES_PATH = DATA_DIR / "linguameta/locales.json"
LINGUAMETA_SCRIPTS_PATH = DATA_DIR / "linguameta/scripts.json"

# pycountry
PYCOUNTRY_ISO_639_3 = DATA_DIR / "pycountry/src/pycountry/databases/iso639-3.json"
PYCOUNTRY_ISO_639_5 = DATA_DIR / "pycountry/src/pycountry/databases/iso639-5.json"
PYCOUNTRY_ISO_3166_1 = DATA_DIR / "pycountry/src/pycountry/databases/iso3166-1.json"
PYCOUNTRY_ISO_3166_2 = DATA_DIR / "pycountry/src/pycountry/databases/iso3166-2.json"
PYCOUNTRY_ISO_3166_3 = DATA_DIR / "pycountry/src/pycountry/databases/iso3166-3.json"
PYCOUNTRY_ISO_15924 = DATA_DIR / "pycountry/src/pycountry/databases/iso15924.json"


@dataclass
class PycountryPaths:
    iso_639_3 = PYCOUNTRY_ISO_639_3
    iso_639_5 = PYCOUNTRY_ISO_639_5
    iso_3166_1 = PYCOUNTRY_ISO_3166_1
    iso_3166_2 = PYCOUNTRY_ISO_3166_2
    iso_3166_3 = PYCOUNTRY_ISO_3166_3
    iso_15924 = PYCOUNTRY_ISO_15924


# Wikipedia
WIKIPEDIA_MAPPING = DATA_DIR / "wikipedia-mapping.json"

# Glotscript
GLOTSCRIPT_MAPPING = DATA_DIR / "glotscript/codes.tsv"

# Glottolog
GLOTTOLOG_PATH = DATA_DIR / "glottolog/languoid.csv"


@dataclass
class LanguageDataPaths:
    json = LINGUAMETA_JSON_PATH
    locales = LINGUAMETA_LOCALES_PATH
    scripts = LINGUAMETA_SCRIPTS_PATH
    overview = LINGUAMETA_OVERVIEW_PATH
    wikipedia = WIKIPEDIA_MAPPING
    glotscript = GLOTSCRIPT_MAPPING
    glottolog = GLOTTOLOG_PATH
