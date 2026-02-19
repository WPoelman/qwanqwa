"""
Basic Usage Example

This example demonstrates the fundamentals of working with qq:
- Loading the database
- Getting a languoid by identifier
- Accessing basic attributes
"""

from qq import Database

# Load the pre-compiled database
db = Database.load()

# Get a language by BCP-47 code (default identifier type)
dutch = db.get("nl")

# Access basic attributes
print(f"Language: {dutch.name}")
print(f"Endonym: {dutch.endonym}")
print()

# Language identifiers
print("Identifiers:")
print(f"  BCP-47:         {dutch.bcp_47}")
print(f"  ISO 639-1:      {dutch.iso_639_1}")
print(f"  ISO 639-2T:     {dutch.iso_639_2t}")
print(f"  ISO 639-2B:     {dutch.iso_639_2b}")
print(f"  ISO 639-3:      {dutch.iso_639_3}")
print(f"  ISO 639-5:      {dutch.iso_639_5}")
print(f"  Glottocode:     {dutch.glottocode}")
print(f"  Wikidata ID:    {dutch.wikidata_id}")
print(f"  Wikipedia Code: {dutch.wikipedia.code}")
print()

# Speaker information
print(f"Speaker count: {dutch.speaker_count:,}")

# Endangerment status
print(f"Endangerment: {dutch.endangerment_status}")

# Writing systems
print("Writing systems:")
for script_code in dutch.script_codes:
    print(f"  - {script_code}")

# Scripts (full objects)
print("\nCanonical scripts:")
for script in dutch.canonical_scripts:
    print(f"  - {script.name} ({script.iso_15924})")

# Regions
print("\nRegions:")
for region in dutch.regions:
    print(f"  - {region.name} ({region.country_code})")
