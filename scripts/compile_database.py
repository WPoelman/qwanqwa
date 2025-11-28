from qq.compile.sources.glotscript import get_glotscript_entries
from qq.compile.sources.glottolog import get_glottolog_entries
from qq.compile.sources.linguameta import (
    get_linguameta_languoid_entries,
    get_linguameta_locale_entries,
    get_linguameta_script_entries,
)
from qq.compile.sources.pycountry import (
    get_pycountry_6393_entries,
    get_pycountry_6395_entries,
    get_pycountry_15924_entries,
    get_pycountry_31661_entries,
    get_pycountry_31662_entries,
    get_pycountry_31663_entries,
)
from qq.compile.sources.wikipedia import get_wikipedia_entries
from qq.constants import LanguageDataPaths, PycountryPaths


def main():
    gl_entries = get_glottolog_entries(LanguageDataPaths.glottolog)

    gs_entries = get_glotscript_entries(LanguageDataPaths.glotscript)

    lm_languoid_entries = get_linguameta_languoid_entries(LanguageDataPaths.overview, LanguageDataPaths.json)
    lm_locale_entries = get_linguameta_locale_entries(LanguageDataPaths.locales)
    lm_script_entries = get_linguameta_script_entries(LanguageDataPaths.scripts)

    pc_6393_entries = get_pycountry_6393_entries(PycountryPaths.iso_639_3)
    pc_6395_entries = get_pycountry_6395_entries(PycountryPaths.iso_639_5)
    pc_31661_entries = get_pycountry_31661_entries(PycountryPaths.iso_3166_1)
    pc_31662_entries = get_pycountry_31662_entries(PycountryPaths.iso_3166_2)
    pc_31663_entries = get_pycountry_31663_entries(PycountryPaths.iso_3166_3)
    pc_15924_entries = get_pycountry_15924_entries(PycountryPaths.iso_15924)

    wiki_entries = get_wikipedia_entries(LanguageDataPaths.wikipedia)

    print(gl_entries[:5])

    print(gs_entries[:5])

    print(lm_languoid_entries[:5])
    print()
    print(lm_locale_entries[:5])
    print()
    print(lm_script_entries[:5])
    print()

    print(pc_6393_entries[0])
    print(pc_6395_entries[0])
    print(pc_31661_entries[0])
    print(pc_31662_entries[0])
    print(pc_31663_entries[0])
    print(pc_15924_entries[0])

    print(wiki_entries[0])


if __name__ == "__main__":
    main()
