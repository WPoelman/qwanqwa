from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qq.interface import GeographicRegion, Languoid, Script


@dataclass(frozen=True)
class ParsedLanguageTag:
    """Simple parsed result of a BCP 47 code.

    This intentionally does not model the full BCP 47 parts, only the
    primary language subtag and script/region pieces such as ``sr-Latn-RS`` and ``deu_Latn``.
    """

    original: str
    normalized: str
    language: str | None
    script: str | None = None
    region: str | None = None


@dataclass(frozen=True)
class ResolvedLanguageTag:
    """A parsed language tag linked to QQ graph entities where possible."""

    original: str
    normalized: str
    language_subtag: str | None
    script_subtag: str | None
    region_subtag: str | None
    languoid: "Languoid | None" = None
    script: "Script | None" = None
    region: "GeographicRegion | None" = None

    @classmethod
    def from_parsed(
        cls,
        parsed: ParsedLanguageTag,
        *,
        languoid: "Languoid | None" = None,
        script: "Script | None" = None,
        region: "GeographicRegion | None" = None,
    ) -> "ResolvedLanguageTag":
        return cls(
            original=parsed.original,
            normalized=parsed.normalized,
            language_subtag=parsed.language,
            script_subtag=parsed.script,
            region_subtag=parsed.region,
            languoid=languoid,
            script=script,
            region=region,
        )


def _is_region_subtag(subtag: str) -> bool:
    return (len(subtag) == 2 and subtag.isalpha()) or (len(subtag) == 3 and subtag.isdigit())


def parse_language_tag(tag: str) -> ParsedLanguageTag:
    """Parse a BCP-47-like tag and return its language/script/region pieces.

    The parser is deliberately permissive:
    - accepts ``-`` and ``_`` separators;
    - normalizes language/script/region casing;
    - ignores extensions/private-use subtags;
    - returns ``language=None`` for private-use-only tags such as ``x-foo``.
    """

    original = tag
    parts = [p for p in tag.replace("_", "-").split("-") if p]
    if not parts:
        return ParsedLanguageTag(original=original, normalized="", language=None)

    # Private-use only tag: x-whatever.
    language = parts[0].lower()
    if language == "x":
        normalized = "-".join(("x", *(p.lower() for p in parts[1:])))
        return ParsedLanguageTag(original=original, normalized=normalized, language=None)

    script: str | None = None
    region: str | None = None
    i = 1
    if i < len(parts) and len(parts[i]) == 4 and parts[i].isalpha():
        script = parts[i].title()
        i += 1

    if i < len(parts) and _is_region_subtag(parts[i]):
        region = parts[i].upper()
        i += 1

    normalized_parts = [language]
    if script:
        normalized_parts.append(script)
    if region:
        normalized_parts.append(region)
    return ParsedLanguageTag(
        original=original,
        normalized="-".join(normalized_parts),
        language=language,
        script=script,
        region=region,
    )
