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
ISO_639_3_TO_2_MAPPING = DATA_DIR / "pycountry/src/pycountry/databases/iso639-3.json"

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
    iso_639_3_to_2 = ISO_639_3_TO_2_MAPPING
