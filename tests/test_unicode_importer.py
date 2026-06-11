from qq.importers.unicode_importer import UnicodeImporter
from qq.internal.entity_resolution import EntityResolver


def test_imports_unicode_script_ranges(tmp_path):
    data_dir = tmp_path / "unicode_ucd"
    data_dir.mkdir()
    (data_dir / "PropertyValueAliases.txt").write_text(
        "sc ; Latn ; Latin\nsc ; Grek ; Greek\n",
        encoding="utf-8",
    )
    (data_dir / "Scripts.txt").write_text(
        "0041..005A ; Latin # uppercase letters\n0061 ; Latin # lowercase a\n0370..0371 ; Greek # Greek letters\n",
        encoding="utf-8",
    )

    importer = UnicodeImporter(EntityResolver())
    importer.import_data(data_dir)

    latin = importer.entity_set.get("script:latn")
    greek = importer.entity_set.get("script:grek")

    assert latin.iso_15924 == "Latn"
    assert latin.unicode_alias == "Latin"
    assert latin.unicode_ranges == ["U+0041..U+005A", "U+0061"]
    assert latin.unicode_character_count == 27
    assert greek.unicode_ranges == ["U+0370..U+0371"]
    assert greek.unicode_character_count == 2
