import os
import sys
from pathlib import Path

_PACKAGE_DIR = Path(__file__).parent
LOCAL_DATA_DIR = _PACKAGE_DIR / "data"

# When running from the repo (dev install), use .sources/ next to pyproject.toml.
# When installed as a package, use the platform-appropriate user data directory.
_REPO_ROOT = _PACKAGE_DIR.parent.parent
if (_REPO_ROOT / "pyproject.toml").exists():
    SOURCES_DIR = _REPO_ROOT / ".sources"
else:
    if sys.platform == "win32":
        _data_home = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        _data_home = Path.home() / "Library" / "Application Support"
    else:
        _data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    SOURCES_DIR = _data_home / "qwanqwa" / "sources"

# These paths are only used by the release/docs scripts in the dev workflow.
DOCS_DIR = _REPO_ROOT / "docs"
README_PATH = _REPO_ROOT / "README.md"
EXAMPLE_PATH = DOCS_DIR / "example.md"
SOURCES_DOCS_PATH = DOCS_DIR / "sources.md"

DEFAULT_DB_FORMAT = "json.gz"
DEFAULT_DB_PATH = LOCAL_DATA_DIR / f"db.{DEFAULT_DB_FORMAT}"

LOG_SEP = "-" * 70
DATETIME_FMT = "%Y%m%d_%H%M%S"
