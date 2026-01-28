import qq.constants as const
from qq.sources.docs_generator import write_sources_documentation


def main():
    write_sources_documentation(const.SOURCES_DIR, const.SOURCES_DOCS_PATH)

    # TODO: update once rebuild is complete!
    # # update example
    # example_text = EXAMPLE_PATH.read_text()
    # am = ld.get("am")
    # am.name_data = {code: am.name_data[code] for code in ["am", "fr", "en"]}
    # new_text = ""
    # # new_text = re.sub(
    # #     r"(```python\n)((.*\n)+)(```)",
    # #     f"\g<1>{pformat(am)}\n\g<4>",
    # #     example_text,
    # #     flags=re.MULTILINE,
    # # )
    # EXAMPLE_PATH.write_text(new_text)

    # # update readme
    # readme_text = README_PATH.read_text()
    # new_text = re.sub(
    #     r"(Number of languoids:) (\d\d\d\d)",
    #     f"\g<1> {len(ld)}",
    #     readme_text,
    # )
    # README_PATH.write_text(new_text)


if __name__ == "__main__":
    main()
