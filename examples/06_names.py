"""
Working with Multilingual Names

This example shows how to:
- Access language names in different languages
- Get endonyms (native names)
- Use name_in() for per-language lookups
"""

from qq import Database

db = Database.load()

# Get a language
german = db.get("de")

print(f"Language: {german.name}")
print()

# Endonym (native name)
print("Native name (endonym):")
print(f"  {german.endonym}")
print()

# Names in different languages using name_in()
# name_in() accepts a BCP-47 code or a Languoid object
print("Names in different languages:")
languages_to_check = ["en", "fr", "es", "it", "nl", "pt", "ru", "zh", "ja", "ar"]

for lang_code in languages_to_check:
    try:
        lang = db.get(lang_code)
        name_in_lang = german.name_in(lang_code)
        lang_name = lang.name or lang_code
        name_str = name_in_lang if name_in_lang else "(not available)"
        print(f"  {lang_name:12s} ({lang_code}): {name_str}")
    except KeyError:
        print(f"  {lang_code}: Not found")
print()

# Check how many translations are available
german_names = db.get_names("de")
if german_names:
    print(f"Total available translations: {len(german_names)}")
else:
    print("Name data not available. Ensure names.zip exists in the data directory.")
print()

# Compare endonyms across languages
print("Endonyms of some common languages:")
major_languages = ["en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ar", "hi", "nl"]

for code in major_languages:
    try:
        lang = db.get(code)
        english = lang.name
        endonym = lang.endonym or "N/A"
        print(f"  {english:12s}: {endonym}")
    except KeyError:
        print(f"  {code}: Not found")
print()

# Access name data properties via name_in()
print("Name data via name_in():")
french = db.get("fr")
name_in_en = french.name_in("en")
name_in_de = french.name_in("de")
print(f"French in English: {name_in_en}")
print(f"French in German: {name_in_de}")

# name_in() also accepts a Languoid object
english = db.get("en")
name_via_languoid = french.name_in(english)
print(f"French via Languoid arg: {name_via_languoid}")
print()

# Find languages with endonyms
print("Checking endonym availability:")
languages = ["en", "am", "ka", "th", "hi", "he"]
for code in languages:
    try:
        lang = db.get(code)
        has_endonym = lang.endonym is not None
        endonym_status = "✓" if has_endonym else "✗"
        english = lang.name or code
        endonym = lang.endonym or "Not available"
        print(f"  {endonym_status} {english:15s}: {endonym}")
    except KeyError:
        print(f"  ✗ {code}: Not found")
