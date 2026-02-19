"""
Normalizing different datasets to a common identifier.

Let's say you have codes from multiple sources
(BCP-47, ISO 639-3, ISO 639-2B, Glottocodes, Wikidata IDs, ...) and
want to normalize everything to one identifier type.

qq can handle this without you needing to know upfront which standard
each code belongs to.
"""

from collections import defaultdict

from qq import Database, IdType

db = Database.load()

# Suppose you're aggregating language data from several sources that each
# use different identifier conventions.
mixed_codes = [
    "nl",  # BCP-47
    "nld",  # ISO 639-3
    "dut",  # ISO 639-2B
    "Q7411",  # Wikidata
    "dutc1256",  # Glottocode
    "fr",  # BCP-47
    "fra",  # ISO 639-3
    "fre",  # ISO 639-2B (French)
    "ell",  # ISO 639-3 (Modern Greek)
    "el",  # BCP-47
    "ZZZZZ",  # Unknown / typo - not resolvable
]

print("Normalizing mixed codes to ISO 639-3:")
print()
print(f"  {'Input':<15} {'ISO 639-3':<12} {'Language name'}")
print(f"  {'-' * 15} {'-' * 12} {'-' * 20}")

for code in mixed_codes:
    try:
        iso = db.convert(code, IdType.ISO_639_3)
        name = db.guess(code).name if iso else "-"
        print(f"  {code:<15} {iso or '(none)':<12} {name}")
    except KeyError:
        print(f"  {code:<15} {'?':<12} not found")

print()

# You can target any identifier type (but not all with have all coverage)
# Here we convert to BCP-47
print("Normalizing to BCP-47:")
print()

source_codes = ["nld", "fra", "deu", "zho", "arb", "spa", "rus", "jpn"]

for code in source_codes:
    bcp = db.convert(code, IdType.BCP_47)
    print(f"  ISO 639-3 '{code}' -> BCP-47 '{bcp}'")

print()

# Another common annoyance: deduplicate datasets that mix two conventions
print("Deduplication example - grouping by canonical ISO 639-3:")
print()


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


# Identifiers and number of tokens for example
dataset_entries = [
    ("en", 1_500_000),
    ("eng", 800_000),
    ("de", 600_000),
    ("deu", 400_000),
    ("ger", 200_000),
    ("zh", 2_000_000),
    ("zho", 1_100_000),
]

# Group by canonical ISO 639-3 code
grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
for code, size in dataset_entries:
    canonical = db.convert(code, IdType.ISO_639_3)
    grouped[canonical].append((code, size))

grand_total = 0
for iso, entries in sorted(grouped.items()):
    lang = db.guess(iso).name
    total = sum(n for _, n in entries)
    grand_total += total
    parts = " + ".join(f"{c} {fmt(n)}" for c, n in entries)
    print(f"  {iso} ({lang}):{' ' * (12 - len(lang))} {parts}  =  {fmt(total)}")
