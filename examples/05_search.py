"""
Searching for Languoids and other entities

This example demonstrates:
- Searching by name
- Filtering results
- Finding languages by properties
"""

from qq import Database, Languoid

db = Database.load()

# Basic name search
print("Searching by name:")
print()

results = db.search("Chinese", limit=10)
print(f"Found {len(results)} results for 'Chinese':")
for lang in results:
    print(f"  - {lang.name} ({lang.iso_639_3 or lang.glottocode})")
print()

# Search with different queries
print("Searching for 'Arabic' variants:")
results = db.search("Arabic", limit=15)
for lang in results[:10]:
    speakers = f"{lang.speaker_count:,}" if lang.speaker_count else "Unknown"
    print(f"  - {lang.name} ({lang.iso_639_3 or lang.glottocode}) - Speakers: {speakers}")
print()

# Filter languages by property
# Endangerment statuses that indicate some degree of risk
print("Finding endangered languages:")
endangered = db.all_endangered

print(f"Total at-risk languages: {len(endangered)}")
print("\nSample of endangered languages:")
for lang in endangered[:10]:
    status = lang.endangerment_status.value if lang.endangerment_status else "Unknown"
    print(f"  - {lang.name} ({lang.iso_639_3 or lang.glottocode}) - Status: {status}")
print()

# Find languages with large speaker populations
print("Languages with > 100 million speakers:")
large_languages = db.query(Languoid, speaker_count=lambda count: count and count > 100_000_000)
# Sort by speaker count
large_languages.sort(key=lambda x: x.speaker_count or 0, reverse=True)

for lang in large_languages:
    speakers = f"{lang.speaker_count:,}"
    print(f"  - {lang.name} ({lang.iso_639_3 or lang.glottocode}): {speakers} speakers")
print()

# Find languages by script
print("Finding languages using Cyrillic script:")
results = db.search_scripts("cyrillic")
cyrillic_languages = results[0].languoids


print(f"Found {len(cyrillic_languages)} languages using Cyrillic")
print("Sample:")
for lang in cyrillic_languages[:10]:
    print(f"  - {lang.name} ({lang.iso_639_3 or lang.glottocode})")
