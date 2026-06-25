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

# List country/territory-level regions
print("Available country/territory regions:")
regions = sorted(db.all_countries, key=lambda region: region.name or region.country_code or region.id)
for region in regions[:5]:
    print(f"  - {region.name or region.id} ({region.country_code})")
print(f"  ... {len(regions)} total")
