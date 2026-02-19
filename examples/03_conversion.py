"""
Converting Between Identifier Types

This example demonstrates:
- Converting between different identifier types
- Batch conversions
- Handling missing conversions
"""

from qq import Database, IdType

db = Database.load()

# Basic conversion
print("Converting between identifier types:")
print()

# BCP-47 to ISO 639-3
iso_code = db.convert("nl", IdType.BCP_47, IdType.ISO_639_3)
print(f"BCP-47 'nl' -> ISO 639-3: {iso_code}")

# ISO 639-3 to Glottocode
glottocode = db.convert("nld", IdType.ISO_639_3, IdType.GLOTTOCODE)
print(f"ISO 639-3 'nld' -> Glottocode: {glottocode}")

# ISO 639-3 to Wikidata
wikidata = db.convert("nld", IdType.ISO_639_3, IdType.WIKIDATA_ID)
print(f"ISO 639-3 'nld' -> Wikidata: {wikidata}")
print()

# Batch conversions
print("Batch conversion from BCP-47 to ISO 639-3:")
bcp_codes = ["en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ar"]

for bcp in bcp_codes:
    iso = db.convert(bcp, IdType.BCP_47, IdType.ISO_639_3)
    lang = db.get(bcp)
    print(f"  {bcp:4s} -> {iso:5s} ({lang.name})")
print()

# Guess the code and convert it to what you're interested in (if you don't know
# what code you're dealing with, but you do know what target code you'd like)
# Can be useful for normalizing datasets to one common code.
gc = db.convert("ell", IdType.GLOTTOCODE)
print(f"Guess for 'ell', glottocode: {gc}")


# Handling missing conversions
print("Handling cases where conversion is not available:")
test_codes = ["en", "tlh", "xyz"]  # tlh might not have all codes, xyz doesn't exist

for code in test_codes:
    try:
        lang = db.guess(code)
        glotto = db.convert(code, IdType.BCP_47, IdType.GLOTTOCODE)
        if glotto:
            print(f"  {code} -> {glotto}")
        else:
            print(f"  {code} -> Glottocode not available")
    except KeyError:
        print(f"  {code} -> Language not found")
print()

# Round-trip conversion
print("Round-trip conversion:")
original = "nld"
bcp = db.convert(original, IdType.ISO_639_3, IdType.BCP_47)
back_to_iso = db.convert(bcp, IdType.BCP_47, IdType.ISO_639_3)
print(f"ISO 639-3 '{original}' -> BCP-47 '{bcp}' -> ISO 639-3 '{back_to_iso}'")
print(f"Round-trip successful: {original == back_to_iso}")
