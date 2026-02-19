from pathlib import Path

from qq.constants import SOURCES_DIR
from qq.internal.build_database import build_database
from qq.internal.storage import load_data
from qq.sources.source_config import SourceConfig


def main():
    target_path = Path(__file__).parent / "test.json"
    build_database(SOURCES_DIR, SourceConfig(), target_path, "json")

    store, resolver = load_data(target_path)


if __name__ == "__main__":
    main()
