from pathlib import Path
from devtools import pformat
import re
from qq.linguameta import LinguaMeta

PROJECT_ROOT = Path(__file__).parent.parent
EXAMPLE_FILE = PROJECT_ROOT / "docs/example.md"
README_FILE = PROJECT_ROOT / "README.md"


def main():
    # make sure dump is up to date
    lm = LinguaMeta.from_raw()
    lm2 = LinguaMeta.from_db()
    if lm.languoids != lm2.languoids:
        lm.dump()

    # update example
    example_text = EXAMPLE_FILE.read_text()
    am = lm.get("am")
    am.name_data = {code: am.name_data[code] for code in ["am", "fr", "en"]}
    new_text = re.sub(
        r"(```python\n)((.*\n)+)(```)",
        f"\g<1>{pformat(am)}\n\g<4>",
        example_text,
        flags=re.MULTILINE,
    )
    EXAMPLE_FILE.write_text(new_text)

    # update readme
    readme_text = README_FILE.read_text()
    new_text = re.sub(
        r"(Number of languoids:) (\d\d\d\d)",
        f"\g<1> {len(lm.languoids)}",
        readme_text,
    )
    README_FILE.write_text(new_text)


if __name__ == "__main__":
    main()
