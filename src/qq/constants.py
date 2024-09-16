from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOCAL_DATA_DIR = Path(__file__).parent / "data"

# LinguaMeta
LINGUAMETA_DUMP_PATH = LOCAL_DATA_DIR / "db.json.gz"
LINGUAMETA_JSON_PATH = DATA_DIR / "linguameta/linguameta/data"
LINGUAMETA_OVERVIEW_PATH = DATA_DIR / "linguameta/linguameta/linguameta.tsv"
LINGUAMETA_LOCALES_PATH = DATA_DIR / "linguameta/linguameta/locales.json"

# Wikipedia
WIKIPEDIA_MAPPING = DATA_DIR / "wikipedia-mapping.json"

# Glotscript
GLOTSCRIPT_MAPPING = DATA_DIR / "glotscript/codes.tsv"


@dataclass
class LinguaMetaPaths:
    json = LINGUAMETA_JSON_PATH
    locales = LINGUAMETA_LOCALES_PATH
    overview = LINGUAMETA_OVERVIEW_PATH
    wikipedia = WIKIPEDIA_MAPPING
    glotscript = GLOTSCRIPT_MAPPING


# Glottolog
LANGUOIDS = DATA_DIR / "glottolog/languoids.csv"

# Grambank
GB_DIR = DATA_DIR / "grambank"
GB_PARAMS = GB_DIR / "gb_parameters.csv"
GB_FEATURES = GB_DIR / "gb_processed.csv"
GB_LANGUAGES = GB_DIR / "gb_languages.csv"
GB_MV_FEATURES = ["GB024", "GB025", "GB065", "GB130", "GB193", "GB203"]
