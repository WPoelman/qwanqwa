from pathlib import Path

from qq import LanguageData


def main():
    path = Path(__file__).parent / "test.db"
    ld = LanguageData.from_raw()
    ld.dump(path)
    LanguageData.from_db(path)
    path.unlink()


if __name__ == "__main__":
    main()
