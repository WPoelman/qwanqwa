"""
Linking NoRaRe Concepts to Concepticon BabelNet Synsets via Concepticon IDs

Both datasets are anchored to the Concepticon concept inventory
(https://concepticon.clld.org), so the link is a direct ID match:

    NoRaRe  datasets/{DS}/{DS}.tsv  →  CONCEPTICON_ID  (numeric string)
    Concepticon zip                 →  concept_id      (numeric string)

NoRaRe data model (norare-data.zip / norare-data/):
  norare.tsv             – one row per variable; columns include DATASET,
                           NAME, STRUCTURE, TYPE, NORARE (norms/ratings/
                           relations), RATING (method), LANGUAGE (ISO 639-1
                           lowercase or ISO 639-3), SOURCE, NOTE
  datasets.tsv           – dataset-level metadata (ID, AUTHOR, YEAR, TAGS,
                           SOURCE_LANGUAGE, TARGET_LANGUAGE, URL, ...)
  datasets/{DS}/{DS}.tsv – one row per concept in that dataset; always has
                           CONCEPTICON_ID and CONCEPTICON_GLOSS, then one or
                           more language columns (e.g. ENGLISH, FRENCH, ...)
                           with the actual word forms measured

Concepticon BabelNet synsets (concepticon.zip):
  concepts_multilingual_senses.tsv  – concept_id, concept_gloss, synset_id
                                      (BabelNet bn:… ID), language (BabelNet
                                      uppercase code), lemma per concept

The script:
  1. Loads both concept inventories.
  2. Links them via the shared Concepticon numeric ID.
  3. Reports coverage statistics and concrete linking examples.
  4. Writes unlinked concept IDs to unlinked_concepts.txt.

Usage:
    uv run python case-studies/linking-datasets/link_concepts.py
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

DATA_DIR = Path(__file__).parent / "data"

NORARE_ZIP = DATA_DIR / "norare-data.zip"
NORARE_TSV = "norare-data/norare.tsv"            # variable-level metadata

CONCEPTICON_ZIP = DATA_DIR / "concepticon.zip"
CONCEPTICON_TSV = "concepticon_synsets/concepts_multilingual_senses.tsv"

# Language columns that appear in per-dataset TSVs
_LANG_COLS = {
    "ENGLISH", "FRENCH", "GERMAN", "SPANISH", "PORTUGUESE", "ITALIAN",
    "CHINESE", "RUSSIAN", "DUTCH", "ARABIC", "JAPANESE", "POLISH",
    "TURKISH", "SWEDISH", "MALAY", "AFRIKAANS", "WELSH", "IRISH",
    "FINNISH", "NORWEGIAN", "DANISH",
}

SEP = "=" * 72


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_norare_concepts(zip_path: Path) -> dict[str, dict]:
    """Load NoRaRe concepts from all per-dataset TSVs inside the zip.

    Iterates over every ``norare-data/datasets/{DS}/{DS}.tsv`` entry,
    collecting CONCEPTICON_ID, CONCEPTICON_GLOSS, the set of datasets that
    cover each concept, and word forms from language columns.

    Returns
    -------
    dict[concepticon_id -> {name, count_datasets, forms: dict[lang -> set]}]
    """
    concepts: dict[str, dict] = {}
    with zipfile.ZipFile(zip_path) as zf:
        tsvs = [
            n for n in zf.namelist()
            if (n.endswith(".tsv")
                and "/datasets/" in n
                and "raw" not in n
                and "-metadata" not in n)
        ]
        for path in tsvs:
            ds_name = path.split("/")[2]   # norare-data/datasets/{DS}/{DS}.tsv
            with zf.open(path) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
                )
                if not reader.fieldnames or "CONCEPTICON_ID" not in reader.fieldnames:
                    continue
                lang_cols = [c for c in reader.fieldnames if c in _LANG_COLS]
                for row in reader:
                    cid = row.get("CONCEPTICON_ID", "").strip()
                    if not cid:
                        continue
                    if cid not in concepts:
                        concepts[cid] = {
                            "name": row.get("CONCEPTICON_GLOSS", "").strip(),
                            "datasets": set(),
                            "forms": {},
                        }
                    concepts[cid]["datasets"].add(ds_name)
                    for lc in lang_cols:
                        form = row.get(lc, "").strip()
                        if form:
                            concepts[cid]["forms"].setdefault(lc.lower(), set()).add(form)
    # Freeze dataset sets to counts
    for info in concepts.values():
        info["count_datasets"] = len(info.pop("datasets"))
    return concepts


def load_norare_variables(zip_path: Path, inner_path: str) -> dict[str, list[dict]]:
    """Load variables from norare.tsv grouped by LANGUAGE code.

    The NORARE column holds the category (norms / ratings / relations).
    """
    by_lang: dict[str, list[dict]] = defaultdict(list)
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
            )
            for row in reader:
                lang = row.get("LANGUAGE", "").strip()
                if not lang or lang == "global":
                    continue
                by_lang[lang].append({
                    "name": row.get("NAME", ""),
                    "category": row.get("NORARE", ""),   # norms/ratings/relations
                    "result": row.get("TYPE", ""),        # AoA, valence, frequency, …
                })
    return dict(by_lang)


def load_norare_languages(zip_path: Path, inner_path: str) -> set[str]:
    """Return the set of unique non-global LANGUAGE codes from norare.tsv."""
    codes: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
            )
            for row in reader:
                lang = row.get("LANGUAGE", "").strip()
                if lang and lang != "global":
                    codes.add(lang)
    return codes


def load_concepticon_synsets(zip_path: Path, inner_path: str) -> dict[str, dict]:
    """Load Concepticon synset data keyed by concept_id.

    Returns
    -------
    dict[concept_id -> {gloss, synset_id, languages: set[str],
                        sample_lemmas: dict[lang -> list[lemma]]}]
    """
    synsets: dict[str, dict] = {}
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
            )
            for row in reader:
                cid = row["concept_id"]
                lang = row["language"]
                lemma = row["lemma"].strip()
                if cid not in synsets:
                    synsets[cid] = {
                        "gloss": row["concept_gloss"],
                        "synset_id": row["synset_id"],
                        "languages": set(),
                        "sample_lemmas": defaultdict(list),
                    }
                synsets[cid]["languages"].add(lang)
                if lemma:
                    synsets[cid]["sample_lemmas"][lang].append(lemma)
    return synsets


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:.1f}%" if total else "-"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading NoRaRe concepts from dataset TSVs...")
    norare = load_norare_concepts(NORARE_ZIP)
    print(f"  {len(norare)} unique concepts across all datasets")

    print("Loading NoRaRe languages and variables...")
    norare_langs = load_norare_languages(NORARE_ZIP, NORARE_TSV)
    norare_vars_by_lang = load_norare_variables(NORARE_ZIP, NORARE_TSV)
    total_vars = sum(len(v) for v in norare_vars_by_lang.values())
    print(f"  {len(norare_langs)} languages, {total_vars} variables")

    print(f"Reading Concepticon BabelNet synsets from {CONCEPTICON_ZIP.name}...")
    concepticon = load_concepticon_synsets(CONCEPTICON_ZIP, CONCEPTICON_TSV)
    print(f"  {len(concepticon)} concept entries loaded\n")

    # -----------------------------------------------------------------------
    # Link: NoRaRe concept <-> Concepticon synset via shared Concepticon ID
    # -----------------------------------------------------------------------
    linked_ids: set[str] = set(norare.keys()) & set(concepticon.keys())
    norare_only: set[str] = set(norare.keys()) - linked_ids
    concepticon_only: set[str] = set(concepticon.keys()) - set(norare.keys())

    print(SEP)
    print("CONCEPT LINKING SUMMARY")
    print(SEP)
    print(f"\n  NoRaRe concepts              : {len(norare):>5}")
    print(f"  Concepticon synset entries   : {len(concepticon):>5}")
    print(
        f"  Linked (shared Concepticon ID): {len(linked_ids):>5}  "
        f"({pct(len(linked_ids), len(norare))} of NoRaRe, "
        f"{pct(len(linked_ids), len(concepticon))} of Concepticon)"
    )
    print(
        f"  In NoRaRe only (no BabelNet synset) : {len(norare_only):>5}  "
        f"({pct(len(norare_only), len(norare))} of NoRaRe)"
    )
    print(
        f"  In Concepticon only (not in NoRaRe) : {len(concepticon_only):>5}  "
        f"({pct(len(concepticon_only), len(concepticon))} of Concepticon)"
    )

    # -----------------------------------------------------------------------
    # Multilingual coverage for linked concepts
    # -----------------------------------------------------------------------
    lang_counts = [len(concepticon[cid]["languages"]) for cid in linked_ids]
    if lang_counts:
        avg_langs = sum(lang_counts) / len(lang_counts)
        print(
            f"\n  Languages per linked concept (BabelNet synsets):  "
            f"min={min(lang_counts)}  avg={avg_langs:.1f}  max={max(lang_counts)}"
        )

    # -----------------------------------------------------------------------
    # NoRaRe variable categories (from norare.tsv NORARE column)
    # -----------------------------------------------------------------------
    print(f"\n  NoRaRe variable categories (across {len(norare_langs)} languages):")
    cat_counter: Counter = Counter()
    for lang_vars in norare_vars_by_lang.values():
        for v in lang_vars:
            cat_counter[v["category"]] += 1
    for cat, cnt in cat_counter.most_common():
        print(f"    {cat:<12}: {cnt} variables")

    # -----------------------------------------------------------------------
    # Detailed linking examples
    # -----------------------------------------------------------------------
    print()
    print(SEP)
    print("CONCEPT LINKING EXAMPLES")
    print(SEP)
    print()
    print("Each example shows a NoRaRe concept linked to its Concepticon")
    print("BabelNet synset, with word forms from both sources.\n")

    showcase = [
        "1277",   # HAND
        "221",    # FIRE
        "948",    # WATER
        "1252",   # HOUSE
        "1313",   # MOON
        "1336",   # EAT
        "1000",   # ANXIETY
        "1390",   # WRONG
    ]
    showcase = [cid for cid in showcase if cid in linked_ids]
    if len(showcase) < 5:
        extra = sorted(
            linked_ids - set(showcase),
            key=lambda c: -norare[c]["count_datasets"],
        )
        showcase.extend(extra[: 8 - len(showcase)])

    for cid in showcase:
        nr = norare[cid]
        cs = concepticon[cid]

        print(f"  Concepticon ID : {cid}")
        print(f"  Concept name   : {nr['name']}")
        print(f"  BabelNet synset: {cs['synset_id']}")
        print(f"  NoRaRe datasets: {nr['count_datasets']}")
        print(f"  Languages in BabelNet synset: {len(cs['languages'])}")

        # Word forms from per-dataset TSV language columns
        if nr["forms"]:
            form_preview = ", ".join(
                f"{lang}={next(iter(forms))}"
                for lang, forms in list(nr["forms"].items())[:5]
            )
            print(f"  NoRaRe forms   : {form_preview}")

        # BabelNet lemmas for a selection of well-known language codes
        sample_langs = ["EN", "DE", "FR", "ES", "ZH", "JA", "AR", "RU"]
        babel_samples = [
            f"{bl}={cs['sample_lemmas'][bl][0]}"
            for bl in sample_langs
            if cs["sample_lemmas"].get(bl)
        ]
        if babel_samples:
            print(f"  BabelNet lemmas: {', '.join(babel_samples)}")

        print()

    # -----------------------------------------------------------------------
    # Concepts in NoRaRe with no matching BabelNet synset
    # -----------------------------------------------------------------------
    print(SEP)
    print("NORARE CONCEPTS WITHOUT CONCEPTICON SYNSET (sample)")
    print(SEP)
    print()
    norare_only_sorted = sorted(
        norare_only,
        key=lambda cid: -norare[cid]["count_datasets"],
    )
    print(f"  {'Concepticon ID':<16} {'Name':<28} {'Datasets':>8}")
    print("  " + "-" * 55)
    for cid in norare_only_sorted[:15]:
        nr = norare[cid]
        print(f"  {cid:<16} {nr['name']:<28} {nr['count_datasets']:>8}")
    if len(norare_only_sorted) > 15:
        print(f"  ... and {len(norare_only_sorted) - 15} more")

    # -----------------------------------------------------------------------
    # Write full unlinked concept list to file
    # -----------------------------------------------------------------------
    out_path = Path(__file__).parent / "unlinked_concepts.txt"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# NoRaRe concepts with no matching Concepticon BabelNet synset\n")
        f.write("# Sorted by dataset coverage (descending)\n\n")
        f.write(f"{'Concepticon_ID':<16} {'Name':<30} {'Datasets':>8}\n")
        f.write("-" * 56 + "\n")
        for cid in norare_only_sorted:
            nr = norare[cid]
            f.write(f"{cid:<16} {nr['name']:<30} {nr['count_datasets']:>8}\n")

    print()
    print(f"Full unlinked concept list written to {out_path.name}")
    print()


if __name__ == "__main__":
    main()