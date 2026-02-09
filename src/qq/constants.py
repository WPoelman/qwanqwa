from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
LOCAL_DATA_DIR = Path(__file__).parent / "data"
SOURCES_DIR = PROJECT_ROOT / ".sources"

README_PATH = PROJECT_ROOT / "README.md"
EXAMPLE_PATH = DOCS_DIR / "example.md"
SOURCES_DOCS_PATH = DOCS_DIR / "sources.md"

DEFAULT_DB_PATH = LOCAL_DATA_DIR / "qwanqwa.pkl.gz"

LOG_SEP = "-" * 70
DATETIME_FMT = "%Y%m%d_%H%M%S"
