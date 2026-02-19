"""
Exploring Relationships Between Entities

This example shows how to:
- Work with graph properties
- Navigate between entities
- Find related languages through shared attributes
"""

from qq import Database
from qq.data_model import RelationType

db = Database.load()

print("Exploring relationships using convenience properties:")
print()

# Get a language and examine its relationships
spanish = db.get("es")
print(f"Language: {spanish.name}")
print()

# Parent-child relationships (convenience properties)
print("Family relationships:")
if spanish.parent:
    print(f"  Parent: {spanish.parent.name}")

if spanish.children:
    print(f"  Children/Dialects: {len(spanish.children)}")
    for child in spanish.children[:5]:
        print(f"    - {child.name or child.id}")
    if len(spanish.children) > 5:
        print(f"    ... and {len(spanish.children) - 5} more")
print()

# Script relationships
print("Script relationships:")
print(f"  Spanish uses {len(spanish.scripts)} script(s):")
for script in spanish.scripts:
    print(f"    - {script.name} ({script.iso_15924})")
print()

# Geographic relationships
print("Geographic relationships:")
print(f"  Spanish is spoken in {len(spanish.regions)} region(s):")
for region in spanish.regions[:10]:
    name = region.name or region.country_code or region.id
    print(f"    - {name}")
if len(spanish.regions) > 10:
    print(f"    ... and {len(spanish.regions) - 10} more")
print()

# Reverse relationships: Script -> Languages
print("Reverse relationships (Script -> Languages):")
latin_script = db.get_script("Latn")

print(f"Script: {latin_script.name} ({latin_script.iso_15924})")
print(f"  Used by {len(latin_script.languoids)} languages")
print("  Sample:")
for lang in latin_script.languoids[:10]:
    print(f"    - {lang.name} ({lang.iso_639_3})")
print(f"    ... and {len(latin_script.languoids) - 10} more")

print()

# Find related languages through shared scripts
print("Finding related languages through shared scripts:")
chinese = db.get("zh")
print(f"Language: {chinese.name}")
print(f"  Uses scripts: {[s.name for s in chinese.scripts]}")

related_langs = chinese.languoids_with_same_script

print(f"\n  Found {len(related_langs)} other languages using the same scripts")
print("  Sample:")
for lang in related_langs[:10]:
    scripts = [s.name for s in lang.canonical_scripts]
    print(f"    - {lang.name} ({lang.iso_639_3}): {', '.join(scripts)}")
print()

# Find languages in the same region
print("Finding languages in the same geographic regions:")
dutch = db.get("nl")
print(f"Language: {dutch.name}")

co_regional_langs = dutch.languoids_in_same_region
print(f"  Found {len(co_regional_langs)} other languages in the same regions")
print("  Sample:")
for lang in co_regional_langs[:10]:
    print(f"    - {lang.name} ({lang.iso_639_3})")
print()

# Sibling languages
print("Sibling languages (same parent):")
german = db.get("de")
print(f"Language: {german.name}")
if german.parent:
    print(f"  Parent: {german.parent.name}")
print(f"  Siblings: {len(german.siblings)}")
for sib in german.siblings[:10]:
    print(f"    - {sib.name} ({sib.iso_639_3})")
print()

# Accessing relationship metadata (for advanced use cases)
print("Accessing relationship metadata (advanced):")
am = db.get("am")
am_relations = am._relations.get(RelationType.USES_SCRIPT, [])

print(f"Language: {am.name}")
for rel in am_relations[:3]:
    script = db.store.get(rel.target_id)
    if script:
        is_canonical = rel.metadata.get("is_canonical", False)
        canonical_marker = " (canonical)" if is_canonical else "(not canonical)"
        print(f"  Uses {script.name}{canonical_marker}")
