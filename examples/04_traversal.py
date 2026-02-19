"""
Traversing Language Families and Relationships

This example shows how to:
- Navigate parent-child relationships in language families
- Get siblings and related languages
- Explore language family trees
"""

from qq import Database

db = Database.load()

# Get a language and its parent
print("Language family relationships")
print()

dutch = db.get("nl")
print(f"Language: {dutch.name}")

# Get parent language
if dutch.parent:
    print(f"  Parent: {dutch.parent.name} ({dutch.parent.iso_639_3 or dutch.parent.glottocode})")

# Get child languages/dialects
if dutch.children:
    print("\n  Children/dialects:")
    for child in dutch.children[:10]:
        print(f"    - {child.name or child.id}")
    if len(dutch.children) > 10:
        print(f"    ... and {len(dutch.children) - 10} more")
print()

# Explore a language family
print("Exploring part of the Romance language family:")
ro = db.guess("ron").parent.parent.parent
print(f"Family: {ro.name}")

# Get all direct children
print(f"Direct children: {len(ro.children)}")

for child in ro.children:
    print(f"  - {child.name} ({child.glottocode})")
print()

# Get siblings (languages with the same parent)
print("Finding sibling languages:")
spanish = db.get("es")
print(f"Language: {spanish.name}")

if spanish.parent:
    print(f"Siblings in '{spanish.parent.name}' family:")
    for sib in spanish.siblings[:10]:
        print(f"  - {sib.name} ({sib.iso_639_3 or sib.glottocode})")
    if len(spanish.siblings) > 10:
        print(f"  ... and {len(spanish.siblings) - 10} more")
print()

# Navigate the full family tree
print("Full ancestry chain:")
dutch = db.get("nl")
print(f"Language: {dutch.name}")
print("  Ancestors (family_tree):")
for ancestor in dutch.family_tree:
    print(f"    -> {ancestor.name or ancestor.id}")
print()

# Get all descendants recursively
print("Getting all descendants:")
if dutch.parent:
    print(f"Parent: {dutch.parent.name}")
    all_descendants = dutch.parent.descendants()
    print(f"  Total descendants: {len(all_descendants)}")
    print("  Sample:")
    for desc in all_descendants[:10]:
        print(f"    - {desc.name}")
    print(f"  ... and {len(all_descendants) - 10} more")
print()

# Working with scripts
print("Languages sharing scripts:")
amharic = db.get("am")
print(f"Language: {amharic.name}")

for script in amharic.canonical_scripts:
    print(f"\nScript: {script.name} ({script.iso_15924})")
    # Use convenience property to get languages
    print(f"  Used by {len(script.languoids)} languages")
    print("  Examples:")
    for lang in script.languoids[:5]:
        print(f"    - {lang.name} ({lang.iso_639_3})")
    print(f"  ... and {len(script.languoids) - 5} more")
print()

# Traversal can also be done across types
# The previous example can also be accessed by: languoid -> script -> languoid
amharic.languoids_with_same_script

# Traversal from languoid -> region -> languoid
print("Languages in same region as Amharic:")
for lang in amharic.languoids_in_same_region[:10]:
    print(f"    - {lang.name} ({lang.iso_639_3 or lang.glottocode})")
print(f"  ... and {len(amharic.languoids_in_same_region) - 5} more")
