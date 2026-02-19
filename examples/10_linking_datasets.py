"""
Linking Datasets with Different Identifier Systems

A common NLP challenge: you have several datasets that each use a different
identifier standard (BCP-47, ISO 639-3, Glottocode, ...) Joining them
often involves CSVs with mappings.

qq resolves any identifier to a shared canonical ID, so you can join
datasets without any manual mapping: even when one dataset uses a
retired code that another has never heard of. You can even define
the ID type you *want* and let qq figure out whatever standard was used and
how to map to the type you want.

This example uses two small inline datasets:
  - Dataset A: machine translation benchmark scores (BCP-47 codes)
  - Dataset B: web corpus sizes in tokens (ISO 639-3 codes, including
               one retired code)
"""

import warnings

from qq import Database, DeprecatedCodeWarning, IdType

db = Database.load()


# MT benchmark scores indexed by BCP-47
MT_SCORES: dict[str, float] = {
    "en": 100.0,  # English
    "nl": 85.3,  # Dutch
    "de": 83.1,  # German
    "fr": 82.7,  # French
    "tr": 68.9,  # Turkish
    "sw": 54.3,  # Swahili
    "qu": 31.2,  # Quechua  (no match in B)
}

# Web corpus sizes (tokens) indexed by ISO 639-3
CORPUS_SIZES: dict[str, int] = {
    "eng": 15_000_000_000,  # English
    "nld": 800_000_000,  # Dutch
    "deu": 1_200_000_000,  # German
    "fra": 900_000_000,  # French
    "swa": 350_000_000,  # Swahili : note: "sw" (BCP-47) == "swa" (ISO 639-3)
    "jpn": 500_000_000,  # Japanese (no match in A)
    "mol": 50_000_000,  # Moldavian: retired ISO 639-3, merged into Romanian
}


def resolve_dataset(entries: dict[str, object], id_type: IdType):
    """
    Map each code in a dataset to its qq canonical ID.

    Returns three buckets:
      resolved   - {canonical_id: (original_code, Languoid, value)}
      retired    - [(original_code, Languoid)] for deprecated codes that still
                   resolved to a successor
      unresolved - [original_code] for codes that couldn't be resolved at all
    """
    resolved: dict[str, tuple] = {}
    retired: list[tuple] = []
    unresolved: list[str] = []

    for code, value in entries.items():
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                lang = db.get(code, id_type)

            resolved[lang.id] = (code, lang, value)

            if caught and issubclass(caught[0].category, DeprecatedCodeWarning):
                retired.append((code, lang))

        except KeyError:
            unresolved.append(code)

    return resolved, retired, unresolved


# Step 1: resolving codes
print("Resolving Dataset A (MT scores, BCP-47)...")
a_by_id, a_retired, a_unresolved = resolve_dataset(MT_SCORES, IdType.BCP_47)
print(f"  {len(a_by_id)} resolved, {len(a_retired)} retired, {len(a_unresolved)} unresolved")

print("Resolving Dataset B (corpus sizes, ISO 639-3)...")
b_by_id, b_retired, b_unresolved = resolve_dataset(CORPUS_SIZES, IdType.ISO_639_3)
print(f"  {len(b_by_id)} resolved, {len(b_retired)} retired, {len(b_unresolved)} unresolved")
print()

# Step 2: Report retired codes
if b_retired:
    print("Retired codes encountered in Dataset B:")
    for code, lang in b_retired:
        print(f"  '{code}' is a retired ISO 639-3 code -> resolved to {lang.name} ({lang.iso_639_3})")
    print()

# Step 3: Compute the join
common_ids = set(a_by_id) & set(b_by_id)
only_a_ids = set(a_by_id) - set(b_by_id)
only_b_ids = set(b_by_id) - set(a_by_id)

print(f"Coverage: {len(common_ids)} in both, {len(only_a_ids)} only in A, {len(only_b_ids)} only in B")
print()

# Step 4: Print the joined table
print("Joined data: languages present in both datasets:")
print(f"  {'Language':<18} {'A code':<8} {'B code':<8} {'MT score':>10} {'Corpus (tokens)':>18}")
print()

for cid in sorted(common_ids, key=lambda x: a_by_id[x][2], reverse=True):
    a_code, lang, mt_score = a_by_id[cid]
    b_code, _, corpus = b_by_id[cid]
    print(f"  {lang.name:<18} {a_code:<8} {b_code:<8} {mt_score:>10.1f} {corpus:>18,}")

print()
print("Note: 'sw' (BCP-47) and 'swa' (ISO 639-3) both resolved to the same")
print("canonical ID automatically: no lookup table needed.")
print()

# Step 5: Languages present in only one dataset
print("Only in A (MT scores, no corpus data):")
for cid in only_a_ids:
    a_code, lang, mt_score = a_by_id[cid]
    print(f"  {lang.name} ({a_code}): MT score {mt_score}")

print()
print("Only in B (corpus data, no MT score):")
for cid in only_b_ids:
    b_code, lang, corpus = b_by_id[cid]
    note = " <- retired code, resolved to successor" if any(c == b_code for c, _ in b_retired) else ""
    print(f"  {lang.name} ({b_code}): {corpus:,} tokens{note}")
