import re

from devtools import pformat

from qq import LanguageData
from qq.constants import EXAMPLE_PATH, README_PATH


def main():
    # make sure dump is up to date
    ld = LanguageData.from_raw()
    ld2 = LanguageData.from_db()
    if (ld.languoids != ld2.languoids) or (ld.scripts != ld2.scripts) or (ld.locales != ld2.locales):
        ld.dump()

    # update example
    example_text = EXAMPLE_PATH.read_text()
    am = ld.get("am")
    am.name_data = {code: am.name_data[code] for code in ["am", "fr", "en"]}
    new_text = re.sub(
        r"(```python\n)((.*\n)+)(```)",
        f"\g<1>{pformat(am)}\n\g<4>",
        example_text,
        flags=re.MULTILINE,
    )
    EXAMPLE_PATH.write_text(new_text)

    # update readme
    readme_text = README_PATH.read_text()
    new_text = re.sub(
        r"(Number of languoids:) (\d\d\d\d)",
        f"\g<1> {len(ld)}",
        readme_text,
    )
    README_PATH.write_text(new_text)


if __name__ == "__main__":
    main()
