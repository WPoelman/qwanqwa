"""
Geographic Information and Regions

This example demonstrates:
- Accessing geographic regions where languages are spoken
- Working with country codes and regions
- Finding languages by region
"""

from qq import Database

db = Database.load()

# Get geographic information for a language
print("Geographic information for Dutch:")
dutch = db.get("nl")

if dutch.regions:
    print("Regions where Dutch is spoken:")
    for region in dutch.regions:
        name = region.name or region.country_code or region.id
        print(f"  - {name} ({region.country_code})")
print()

# Find languages spoken in a specific country
print("Finding languages spoken in a country:")
belgium = db.get_region("BE")

print(f"Region: {belgium.name} ({belgium.country_code})")
print(f"Languages / dialects spoken: {len(belgium.languoids)}")
for lang in belgium.languoids[:10]:
    print(f"  - {lang.name} ({lang.iso_639_3 or lang.glottocode})")
print()

# Scripts in use in a region
am = db.get_region("AM")
print(f"Scripts used in: {am.name}")
for script in am.scripts[:10]:
    print(f"  - {script.name} ({script.iso_15924})")
print()

# Explore region hierarchy (subdivisions)
print("Region hierarchy (subdivisions):")
usa = db.get_region("US")
print(f"Country: {usa.name} ({usa.country_code})")
if usa.subdivisions:
    print(f"  Subdivisions: {len(usa.subdivisions)}")
    for sub in usa.subdivisions[:5]:
        print(f"    - {sub.name} ({sub.subdivision_code})")
    if len(usa.subdivisions) > 5:
        print(f"    ... and {len(usa.subdivisions) - 5} more")
