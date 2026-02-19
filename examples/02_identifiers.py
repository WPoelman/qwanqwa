"""
Working with Different Identifier Types

This example shows how to:
- Get languages using different identifier types
- Use the guess() method for automatic identifier detection
- Access NLLB-style codes
- Look up by Wikipedia language edition code
- Handle retired (deprecated) language codes
"""

import warnings

from qq import Database, DeprecatedCodeWarning, IdType

db = Database.load()

# Get a language using different identifier types
print("Getting the same language using different identifiers:")
print()

# By BCP-47 (default)
lang1 = db.get("nl", id_type=IdType.BCP_47)
print(f"BCP-47 'nl': {lang1.name}")

# By ISO 639-3
lang2 = db.get("nld", id_type=IdType.ISO_639_3)
print(f"ISO 639-3 'nld': {lang2.name}")

# By Glottocode
lang3 = db.get("dutc1256", id_type=IdType.GLOTTOCODE)
print(f"Glottocode 'dutc1256': {lang3.name}")

# They all refer to the same canonical entity
assert lang1.id == lang2.id == lang3.id
print(f"\nAll resolve to the same canonical ID: {lang1.id}")
print()

# Using guess() to automatically detect identifier type
print("Using guess() to auto-detect identifier type:")
examples = ["nl", "nld", "dut", "neth1247", "Q7411"]
for code in examples:
    try:
        lang = db.guess(code)
        print(f"  '{code}' -> {lang.name} ({lang.iso_639_3})")
    except KeyError:
        print(f"  '{code}' -> Not found")
print()

# NLLB-style codes (language + script combinations)
print("NLLB-style codes:")
am = db.get("am")
nllb = am.nllb_codes()
if nllb:
    print(f"  Amharic ISO 639-3 based: {nllb}")
    print(f"  Amharic BCP-47 based: {am.nllb_codes(use_bcp_47=True)}")
else:
    print("  (NLLB codes not available - no script relations)")
print()

# Checking for missing identifiers
print("Handling missing identifiers:")
arabic = db.get("ar")
print(f"Arabic ISO 639-2B: {arabic.iso_639_2b or 'Not available'}")
print(f"Arabic Glottocode: {arabic.glottocode or 'Not available'}")
print()

# Wikipedia language edition codes
# qq registers all active Wikipedia editions (and historical compound codes used
# by datasets like BabelNet) so you can look up by Wikipedia code directly.
print("Wikipedia language edition codes:")
cantonese = db.get("zh-yue", id_type=IdType.WIKIPEDIA)
print(f"  'zh-yue' (old compound code): {cantonese.name} ({cantonese.iso_639_3})")

classical = db.get("zh-classical", id_type=IdType.WIKIPEDIA)
print(f"  'zh-classical': {classical.name} ({classical.iso_639_3})")

simple_en = db.get("simple", id_type=IdType.WIKIPEDIA)
print(f"  'simple' (Simple English): {simple_en.name} ({simple_en.bcp_47})")

# Wikipedia edition info is also available on the Languoid itself
dutch = db.get("nl")
if dutch.wikipedia:
    print(f"  Dutch Wikipedia: {dutch.wikipedia.url} (code: {dutch.wikipedia.code})")
print()

# Retired (deprecated) codes
# The ISO 639-3 standard occasionally retires codes. qq tracks these via the
# SIL retirement table and issues a DeprecatedCodeWarning when you use one,
# while still returning the correct successor entity.
print("Retired language codes:")
print()

# "mol" (Moldavian) was retired in 2008 and merged into "ron" (Romanian).
# Using it will trigger a DeprecatedCodeWarning but still return Romanian.
print("  Using retired code 'mol' (Moldavian -> Romanian):")
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    romanian = db.get("mol", IdType.ISO_639_3)

if caught and issubclass(caught[0].category, DeprecatedCodeWarning):
    print(f"  Warning: {caught[0].message}")
print(f"  Resolved to: {romanian.name} ({romanian.iso_639_3})")
print()

# Retired codes can also be split up into multiple codes, you get a warning and
# suggested remedy. Here the actual code is returned since you have to choose
# what replacement you want.
db.get("ccy", IdType.ISO_639_3)

# You can also check upfront whether a code is retired without triggering an
# exception or a warning:
print("  Checking retirement status directly:")
is_retired = db.resolver.is_deprecated(IdType.ISO_639_3, "mol")
print(f"  'mol' is retired: {is_retired}")
is_retired = db.resolver.is_deprecated(IdType.ISO_639_3, "nld")
print(f"  'nld' is retired: {is_retired}")
