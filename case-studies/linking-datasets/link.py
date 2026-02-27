"""
Linking Colexification Datasets via qq Language Identifiers

Five lexical/etymological datasets, each using a different identifier standard:
  1. Concepticon BabelNet synsets : BabelNet codes: primarily uppercase ISO 639-1
                                     (e.g. 'IT', 'ZH'), ISO 639-3 for historical
                                     languages (e.g. 'AKK', 'ANG'), and Wikipedia
                                     compound codes (e.g. 'BAT_SMG', 'ZH_YUE')
  2. WordNet synsets              : same BabelNet convention as Concepticon
  3. Etymon (Etymological Wordnet): ISO 639-3 lowercase (e.g. 'eng', 'deu'), plus
                                     ISO 639-5 family codes (e.g. 'nah') and proto-
                                     language codes (p_gem, p_ine, ...) that strip to
                                     ISO 639-5 (e.g. p_gem -> gem)
  4. Phonotacticon                : Glottocodes + ISO 639-3 codes
  5. NoRaRe (norare-data)        : ISO 639-1 lowercase (e.g. 'en', 'de') from
                                     norare.tsv LANGUAGE column, plus a handful of
                                     ISO 639-3 codes (e.g. 'eng', 'tpi'); the
                                     special value 'global' is ignored

qq resolves all five to a shared canonical ID

Note: reading the two large files (concepticon ~760 MB, WordNet ~230 MB) takes about
a minute. Only the language column is parsed; no data is loaded into memory.

Usage:
    uv run python case-studies/linking-datasets/link.py
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

from qq import Database
from qq.constants import LOG_SEP
from qq.data_model import IdType

# Some rows in the large TSV files have very long fields (e.g. sense keys)
csv.field_size_limit(sys.maxsize)


DATA_DIR = Path(__file__).parent / "data"


def collect_codes(zip_path: Path, inner_path: str, col_names: list[str], sep: str = "\t") -> set[str]:
    """Stream through a file inside a zip, collecting unique
    values from one or more columns: without loading the full file into memory."""
    codes: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter=sep)
            for row in reader:
                for col in col_names:
                    if val := row.get(col, "").strip():
                        codes.add(val)
    return codes


def collect_codes_etymon(zip_path: Path, inner_path: str) -> set[str]:
    """Collect language codes from Etymon's headerless TSV.

    Each line has the format: {lang}: {lemma}\\t{relation}\\t{lang}: {lemma}
    Language codes are extracted from column 0 and column 2.
    """
    codes: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8"):
                parts = line.rstrip("\n").split("\t")
                for col in (0, 2):
                    if col < len(parts):
                        field = parts[col].strip()
                        if ": " in field:
                            lang = field.split(": ", 1)[0]
                            if lang:
                                codes.add(lang)
    return codes


def collect_codes_phonotacticon(zip_path: Path, inner_path: str, resolver) -> tuple[set[str], set[str]]:
    """Collect Glottocodes and ISO 639-3 codes from Phonotacticon CSV."""
    glottocodes: set[str] = set()
    iso_codes: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))
            for row in reader:
                if gc := row.get("Glottocode", "").strip():
                    glottocodes.add(gc)
                if iso := row.get("ISO", "").strip():
                    iso_codes.add(iso)
    return glottocodes, iso_codes


def collect_codes_norare(zip_path: Path, inner_path: str) -> tuple[set[str], set[str]]:
    """Collect language codes from norare-data/norare.tsv (inside zip).

    The LANGUAGE column holds mostly ISO 639-1 lowercase codes (e.g. 'en',
    'de') with a few ISO 639-3 codes (e.g. 'eng', 'tpi').  The special value
    'global' carries no language information and is skipped.

    Returns
    -------
    bcp47_codes : ISO 639-1 / BCP-47 two-letter codes (lowercase)
    iso3_codes  : ISO 639-3 three-letter codes
    """
    bcp47_codes: set[str] = set()
    iso3_codes: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_path) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t")
            for row in reader:
                lang = row.get("LANGUAGE", "").strip()
                if not lang or lang == "global":
                    continue
                if len(lang) == 2:
                    bcp47_codes.add(lang)
                else:
                    iso3_codes.add(lang)
    return bcp47_codes, iso3_codes


def resolve(
    resolver,
    codes: set[str],
    id_types: list[tuple[IdType, Callable[[str], str] | None]],
) -> tuple[dict[str, str], set[str]]:
    """Resolve a set of codes to qq canonical IDs, trying multiple identifier types in order.

    Returns:
        resolved:   {original_code: canonical_id}
        unresolved: codes that could not be resolved by any means
    """
    resolved: dict[str, str] = {}
    unresolved: set[str] = set()
    for code in sorted(codes):
        canonical = None
        for id_type, normalize in id_types:
            lookup = normalize(code) if normalize else code
            canonical = resolver.resolve(id_type, lookup)
            if canonical:
                break
        if canonical:
            resolved[code] = canonical
        else:
            unresolved.add(code)
    return resolved, unresolved


def resolve_phonotacticon(resolver, glottocodes: set[str], iso_codes: set[str]) -> tuple[dict[str, str], set[str], int]:
    """Resolve Phonotacticon codes: try Glottocode first, then ISO 639-3.

    Returns:
        resolved:        {original_code: canonical_id} (using Glottocode as key where possible)
        unresolved:      codes that could not be resolved
        total_languages: unique language count (denominator for coverage %)
    """
    resolved: dict[str, str] = {}
    unresolved: set[str] = set()
    for gc in sorted(glottocodes):
        canonical = resolver.resolve(IdType.GLOTTOCODE, gc)
        if canonical:
            resolved[gc] = canonical
        else:
            unresolved.add(gc)
    # ISO codes that represent languages not already covered by a Glottocode
    resolved_canonicals = set(resolved.values())
    extra_languages = 0
    for iso in sorted(iso_codes):
        canonical = resolver.resolve(IdType.ISO_639_3, iso)
        if canonical and canonical not in resolved_canonicals:
            resolved[iso] = canonical
            extra_languages += 1
        elif canonical is None:
            unresolved.add(iso)
            extra_languages += 1
    # total = Glottocode languages + additional languages only reachable via ISO
    return resolved, unresolved, len(glottocodes) + extra_languages


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:.1f}%" if total else "-"


def lang_label(ld: Database, canonical_id: str) -> str:
    lang = ld.store.get(canonical_id)
    return lang.name if lang and lang.name else canonical_id  # type: ignore[union-attr]


def main() -> None:
    print("Loading qq database...")
    ld = Database.load(names_path=None)
    resolver = ld.resolver
    print(f"Loaded {len(ld.all_languoids)} languoids\n")

    print("Reading Concepticon BabelNet synsets (large file, ~1 min)...")
    concepticon_codes = collect_codes(
        DATA_DIR / "concepticon.zip",
        "concepticon_synsets/concepts_multilingual_senses.tsv",
        col_names=["language"],
        sep="\t",
    )
    print(f"  {len(concepticon_codes)} unique codes found")

    print("Reading WordNet synsets (large file, ~30 s)...")
    wn_codes = collect_codes(
        DATA_DIR / "wordnet.zip",
        "wn_synsets.csv",
        col_names=["LANG"],
        sep="\t",
    )
    print(f"  {len(wn_codes)} unique codes found")

    print("Reading Etymon crosslingual data...")
    etymon_codes = collect_codes_etymon(
        DATA_DIR / "etymon.zip",
        "etymon/etymwn.tsv",
    )
    print(f"  {len(etymon_codes)} unique codes found")

    print("Reading Phonotacticon data...")
    phono_glottocodes, phono_iso_codes = collect_codes_phonotacticon(
        DATA_DIR / "phonotacticon.zip",
        "Phonotacticon/Phonotacticon1_0.csv",
        resolver,
    )
    print(f"  {len(phono_glottocodes)} Glottocodes, {len(phono_iso_codes)} ISO codes found\n")

    print("Reading NoRaRe data...")
    norare_bcp47_codes, norare_iso3_codes = collect_codes_norare(
        DATA_DIR / "norare-data.zip",
        "norare-data/norare.tsv",
    )
    norare_total = len(norare_bcp47_codes) + len(norare_iso3_codes)
    print(f"  {len(norare_bcp47_codes)} BCP-47 codes, {len(norare_iso3_codes)} ISO 639-3 codes found\n")

    # --- Resolve each set through qq ---

    # BabelNet uses uppercase codes. Primarily ISO 639-1 (e.g. NL -> nl), but also
    # ISO 639-3 for historical/ancient languages (e.g. AKK -> akk, ANG -> ang),
    # ISO 639-5 family codes, and Wikipedia-style compound codes (e.g. BAT_SMG ->
    # bat-smg -> resolved via IdType.WIKIPEDIA). Try all in order.
    babelnet_lookup: list[tuple[IdType, Any]] = [
        (IdType.BCP_47, str.lower),
        (IdType.ISO_639_3, str.lower),
        (IdType.ISO_639_5, str.lower),
        (IdType.WIKIPEDIA, lambda c: c.lower().replace("_", "-")),
    ]
    concepticon_resolved, concepticon_unresolved = resolve(resolver, concepticon_codes, babelnet_lookup)
    wn_resolved, wn_unresolved = resolve(resolver, wn_codes, babelnet_lookup)

    # Etymon uses ISO 639-3; also try ISO 639-5 for family codes (e.g. 'nah').
    # Proto-language codes (p_gem, p_ine, ...) strip to ISO 639-5 family codes.
    etymon_lookup: list[tuple[IdType, Any]] = [
        (IdType.ISO_639_3, None),
        (IdType.ISO_639_5, None),
        (IdType.ISO_639_5, lambda c: c[2:] if c.startswith("p_") else c),
    ]
    etymon_resolved, etymon_unresolved = resolve(resolver, etymon_codes, etymon_lookup)

    # Phonotacticon uses Glottocodes primarily, ISO 639-3 as fallback
    phono_resolved, phono_unresolved, phono_total = resolve_phonotacticon(resolver, phono_glottocodes, phono_iso_codes)

    # NoRaRe: BCP-47 (ISO 639-1 lowercase) first, then ISO 639-3 as fallback
    norare_lookup: list[tuple[IdType, Any]] = [
        (IdType.BCP_47, None),
        (IdType.ISO_639_3, None),
    ]
    norare_bcp47_resolved, norare_bcp47_unresolved = resolve(resolver, norare_bcp47_codes, norare_lookup)
    norare_iso3_resolved, norare_iso3_unresolved = resolve(resolver, norare_iso3_codes, norare_lookup)
    norare_resolved = {**norare_bcp47_resolved, **norare_iso3_resolved}
    norare_unresolved = norare_bcp47_unresolved | norare_iso3_unresolved

    print(LOG_SEP)
    print("DATASET SUMMARY")
    print(LOG_SEP)

    rows = [
        (
            "Concepticon (BabelNet)",
            "BabelNet (ISO 639-1 + ISO 639-3 + ISO 639-5 + Wikipedia codes, uppercase)",
            len(concepticon_codes),
            len(concepticon_resolved),
            concepticon_unresolved,
        ),
        (
            "WordNet synsets",
            "BabelNet (ISO 639-1 + ISO 639-3 + ISO 639-5 + Wikipedia codes, uppercase)",
            len(wn_codes),
            len(wn_resolved),
            wn_unresolved,
        ),
        (
            "Etymon",
            "ISO 639-3 lowercase + ISO 639-5 (incl. proto-language codes as p_* -> ISO 639-5)",
            len(etymon_codes),
            len(etymon_resolved),
            etymon_unresolved,
        ),
        (
            "Phonotacticon",
            "Glottocode + ISO 639-3",
            phono_total,
            len(phono_resolved),
            phono_unresolved,
        ),
        (
            "NoRaRe",
            "ISO 639-1 lowercase (BCP-47) + ISO 639-3 (LANGUAGE column of norare.tsv)",
            norare_total,
            len(norare_resolved),
            norare_unresolved,
        ),
    ]

    for name, id_std, total, n_resolved, unresolved in rows:
        print(f"\n{name}")
        print(f"  Identifier standard : {id_std}")
        print(f"  Unique codes        : {total}")
        print(f"  Resolved by qq      : {n_resolved} / {total}  ({pct(n_resolved, total)})")
        if unresolved:
            print(f"  Unresolved ({len(unresolved)})      : {', '.join(sorted(unresolved))}")

    # --- Cross-dataset intersection ---

    concepticon_ids = set(concepticon_resolved.values())
    wn_ids = set(wn_resolved.values())
    etymon_ids = set(etymon_resolved.values())
    phono_ids = set(phono_resolved.values())
    norare_ids = set(norare_resolved.values())

    all_five = concepticon_ids & wn_ids & etymon_ids & phono_ids & norare_ids
    all_four = concepticon_ids & wn_ids & etymon_ids & phono_ids
    all_three = concepticon_ids & wn_ids & etymon_ids

    print()
    print(LOG_SEP)
    print("CROSS-DATASET COVERAGE")
    print(LOG_SEP)
    print(
        f"\n  Unique languages: Concepticon {len(concepticon_ids)}, WordNet {len(wn_ids)}, "
        f"Etymon {len(etymon_ids)}, Phonotacticon {len(phono_ids)}, NoRaRe {len(norare_ids)}"
    )
    print(f"\n  Concepticon only              : {len(concepticon_ids - wn_ids - etymon_ids - phono_ids - norare_ids):>5}")
    print(f"  WordNet only                  : {len(wn_ids - concepticon_ids - etymon_ids - phono_ids - norare_ids):>5}")
    print(f"  Etymon only                   : {len(etymon_ids - concepticon_ids - wn_ids - phono_ids - norare_ids):>5}")
    print(f"  Phonotacticon only            : {len(phono_ids - concepticon_ids - wn_ids - etymon_ids - norare_ids):>5}")
    print(f"  NoRaRe only                   : {len(norare_ids - concepticon_ids - wn_ids - etymon_ids - phono_ids):>5}")
    print(f"  Concepticon ∩ WordNet          : {len(concepticon_ids & wn_ids):>5}")
    print(f"  Concepticon ∩ Etymon           : {len(concepticon_ids & etymon_ids):>5}")
    print(f"  Concepticon ∩ Phonotacticon    : {len(concepticon_ids & phono_ids):>5}")
    print(f"  Concepticon ∩ NoRaRe           : {len(concepticon_ids & norare_ids):>5}")
    print(f"  WordNet ∩ Etymon               : {len(wn_ids & etymon_ids):>5}")
    print(f"  WordNet ∩ Phonotacticon        : {len(wn_ids & phono_ids):>5}")
    print(f"  WordNet ∩ NoRaRe               : {len(wn_ids & norare_ids):>5}")
    print(f"  Etymon ∩ Phonotacticon         : {len(etymon_ids & phono_ids):>5}")
    print(f"  Etymon ∩ NoRaRe                : {len(etymon_ids & norare_ids):>5}")
    print(f"  Phonotacticon ∩ NoRaRe         : {len(phono_ids & norare_ids):>5}")
    print(f"  All three (excl. others)       : {len(all_three):>5}")
    print(f"  All four (excl. NoRaRe)        : {len(all_four):>5}")
    print(f"  All five datasets              : {len(all_five):>5} (automatic, no mapping needed)")

    # --- Concrete linking examples ---

    # Build reverse maps: canonical_id -> code for each dataset
    concepticon_by_id = {v: k for k, v in concepticon_resolved.items()}
    wn_by_id = {v: k for k, v in wn_resolved.items()}
    etymon_by_id = {v: k for k, v in etymon_resolved.items()}
    phono_by_id = {v: k for k, v in phono_resolved.items()}
    norare_by_id = {v: k for k, v in norare_resolved.items()}

    print()
    print(LOG_SEP)
    print("CROSS-DATASET LINKING EXAMPLES")
    print(LOG_SEP)
    print()
    print("The same language expressed in each dataset's identifier system,")
    print("all resolved to the same qq canonical ID:\n")

    # Pick a selection of well-known languages that appear in all four
    showcase_codes = [
        (IdType.ISO_639_3, "nld"),  # Dutch
        (IdType.ISO_639_3, "deu"),  # German
        (IdType.ISO_639_3, "arb"),  # Arabic
        (IdType.ISO_639_3, "cmn"),  # Mandarin
        (IdType.ISO_639_3, "swa"),  # Swahili
        (IdType.ISO_639_3, "tur"),  # Turkish
        (IdType.ISO_639_3, "rus"),  # Russian
        (IdType.ISO_639_3, "jpn"),  # Japanese
    ]

    header = (
        f"  {'Language':<22} {'Canonical ID':<14} {'Concepticon':<14} "
        f"{'WordNet':<14} {'Etymon':<12} {'Phonotacticon':<14} {'NoRaRe':<10}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    shown = 0
    for id_type, code in showcase_codes:
        canonical = resolver.resolve(id_type, code)
        if not canonical:
            continue
        c_code = concepticon_by_id.get(canonical, "-")
        w_code = wn_by_id.get(canonical, "-")
        e_code = etymon_by_id.get(canonical, "-")
        p_code = phono_by_id.get(canonical, "-")
        n_code = norare_by_id.get(canonical, "-")
        if c_code == "-" and w_code == "-" and e_code == "-" and p_code == "-" and n_code == "-":
            continue
        name = lang_label(ld, canonical)
        print(f"  {name:<22} {canonical:<14} {c_code:<14} {w_code:<14} {e_code:<12} {p_code:<14} {n_code:<10}")
        shown += 1

    if shown == 0:
        # Fall back to top-N from the intersection
        for canonical in sorted(all_five)[:8]:
            name = lang_label(ld, canonical)
            c_code = concepticon_by_id.get(canonical, "-")
            w_code = wn_by_id.get(canonical, "-")
            e_code = etymon_by_id.get(canonical, "-")
            p_code = phono_by_id.get(canonical, "-")
            n_code = norare_by_id.get(canonical, "-")
            print(f"  {name:<22} {canonical:<14} {c_code:<14} {w_code:<14} {e_code:<12} {p_code:<14} {n_code:<10}")

    print()

    unresolved_path = Path(__file__).parent / "unresolved.txt"
    with unresolved_path.open("w") as f:
        for dataset, codes in [
            ("Concepticon (BabelNet)", concepticon_unresolved),
            ("WordNet synsets", wn_unresolved),
            ("Etymon", etymon_unresolved),
            ("Phonotacticon", phono_unresolved),
            ("NoRaRe", norare_unresolved),
        ]:
            f.write(f"# {dataset}\n")
            for code in sorted(codes):
                f.write(f"{code}\n")
            f.write("\n")
    print(f"Unresolved codes written to {unresolved_path.name}")


if __name__ == "__main__":
    main()
