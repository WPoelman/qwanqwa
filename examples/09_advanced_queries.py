"""
Advanced Queries and Filtering

This example demonstrates:
- Complex filtering and queries
- Combining multiple criteria
- Statistical analysis of the database
"""

from qq import Database, EndangermentStatus, Languoid

db = Database.load()

# Get all languoids for analysis
all_languoids = db.all_languoids
total_langs = len(all_languoids)
print(f"Total languoids in database: {total_langs}")
print()

# Filter by multiple criteria using query()
print("Complex filtering: Large, safe languages using Latin script")
print()

large_safe_latin = db.query(
    Languoid,
    speaker_count=lambda x: x >= 10_000_000,
    endangerment_status=EndangermentStatus.NOT_ENDANGERED,
    canonical_scripts=lambda scripts: "Latn" in [s.iso_15924 for s in scripts],
)

# Sort by speaker count
large_safe_latin.sort(key=lambda x: x.speaker_count or 0, reverse=True)

print(f"Found {len(large_safe_latin)} languages matching all criteria:")
for lang in large_safe_latin[:15]:
    iso = lang.iso_639_3 or "N/A"
    speakers = f"{lang.speaker_count:,}" if lang.speaker_count else "Unknown"
    print(f"  - {lang.name:20s} ({iso}): {speakers} speakers")
print()

# Statistical analysis
print("Database statistics:")
print()

# Count by endangerment status
endangerment_counts: dict[str, int] = {}
langs_with_status = db.query(Languoid, endangerment_status=lambda s: s is not None)
for lang in langs_with_status:
    status_name = lang.endangerment_status.value
    endangerment_counts[status_name] = endangerment_counts.get(status_name, 0) + 1

print("Languages by endangerment status:")
for status, count in sorted(endangerment_counts.items(), key=lambda x: x[1], reverse=True):
    percentage = (count / total_langs) * 100
    print(f"  {status:30s}: {count:5d} ({percentage:.1f}%)")
print()

# Script usage statistics
print("Most common writing systems:")
script_counts: dict[str, int] = {}
for lang in all_languoids:
    if lang.script_codes:
        for script_code in lang.script_codes:
            script_counts[script_code] = script_counts.get(script_code, 0) + 1

# Build a name lookup for scripts
script_name_map = {s.iso_15924: s.name for s in db.all_scripts if s.iso_15924}

sorted_scripts = sorted(script_counts.items(), key=lambda x: x[1], reverse=True)
print("Top 15 scripts by number of languages:")
for script_code, count in sorted_scripts[:15]:
    script_name = script_name_map.get(script_code, script_code)
    print(f"  {script_name:25s} ({script_code}): {count:4d} languages")
print()

# Speaker population statistics
print("Speaker population statistics:")
languages_with_speakers = db.query(Languoid, speaker_count=lambda s: s and s > 0)

if languages_with_speakers:
    speaker_counts = [lang.speaker_count for lang in languages_with_speakers]
    total_speakers = sum(speaker_counts)
    avg_speakers = total_speakers / len(speaker_counts)
    median_speakers = sorted(speaker_counts)[len(speaker_counts) // 2]

    print(f"  Languages with speaker data: {len(languages_with_speakers)}")
    print(f"  Total speakers (sum): {total_speakers:,}")
    print(f"  Average speakers: {int(avg_speakers):,}")
    print(f"  Median speakers: {int(median_speakers):,}")
print()

# Find language families with most children
print("Largest language families (by number of children):")
family_sizes = []

for lang in all_languoids:
    if lang.children and len(lang.children) > 10:
        family_sizes.append((lang.name, len(lang.children)))

family_sizes.sort(key=lambda x: x[1], reverse=True)

for family_name, size in family_sizes[:10]:
    print(f"  {family_name:30s}: {size:3d} children")
print()

# Identifier coverage analysis (example)
print("Identifier coverage:")
stats = {
    "ISO 639-3": sum(1 for lang in all_languoids if lang.iso_639_3),
    "ISO 639-2B": sum(1 for lang in all_languoids if lang.iso_639_2b),
    "Glottocode": sum(1 for lang in all_languoids if lang.glottocode),
    "Wikidata": sum(1 for lang in all_languoids if lang.wikidata_id),
}

for id_type, count in stats.items():
    percentage = (count / len(all_languoids)) * 100
    print(f"  {id_type:15s}: {count:5d} ({percentage:.1f}%)")
