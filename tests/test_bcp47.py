import pytest

from qq.bcp47 import parse_language_tag


def test_parse_language_tag_accepts_single_language_subtag():
    result = parse_language_tag("nld")

    assert result.original == "nld"
    assert result.normalized == "nld"
    assert result.language == "nld"
    assert result.script is None
    assert result.region is None


@pytest.mark.parametrize(
    ("tag", "normalized", "language", "script", "region"),
    [
        ("NL", "nl", "nl", None, None),
        ("nl-Latn-NL", "nl-Latn-NL", "nl", "Latn", "NL"),
        ("nl_latn_nl", "nl-Latn-NL", "nl", "Latn", "NL"),
        ("nld_Latn", "nld-Latn", "nld", "Latn", None),
        ("zh-Hant-TW", "zh-Hant-TW", "zh", "Hant", "TW"),
        ("es-419", "es-419", "es", None, "419"),
        ("nan-tw", "nan-TW", "nan", None, "TW"),
    ],
)
def test_parse_language_tag_normalizes_common_language_tags(tag, normalized, language, script, region):
    result = parse_language_tag(tag)

    assert result.original == tag
    assert result.normalized == normalized
    assert result.language == language
    assert result.script == script
    assert result.region == region


def test_parse_language_tag_ignores_variant_subtags():
    result = parse_language_tag("rm-vallader")

    assert result.normalized == "rm"
    assert result.language == "rm"
    assert result.script is None
    assert result.region is None


def test_parse_language_tag_ignores_extension_subtags():
    result = parse_language_tag("de-DE-u-co-phonebk")

    assert result.normalized == "de-DE"
    assert result.language == "de"
    assert result.script is None
    assert result.region == "DE"


def test_parse_language_tag_returns_none_for_private_use_only():
    result = parse_language_tag("x-qq")

    assert result.normalized == "x-qq"
    assert result.language is None
    assert result.script is None
    assert result.region is None


def test_parse_language_tag_handles_empty_input():
    result = parse_language_tag("")

    assert result.normalized == ""
    assert result.language is None
    assert result.script is None
    assert result.region is None
