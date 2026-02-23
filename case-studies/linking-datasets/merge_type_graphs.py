"""
Merge concept graphs by rating type, intersected with colexification edges.

For each rating type (AoA, valence, frequency, …):
  - Nodes: every concept that has a rating of this type in at least one language
  - Edges: taken from the colexification graph (concepts sharing a lemma in
           some language), restricted to pairs where BOTH endpoints are rated
  - Edge data:
      · colexification metadata (languages, lemmas, n_languages, n_instances)
      · source_ratings / target_ratings  — mean rating per language at each end
      · langs_rated_both   — languages where BOTH endpoints have a rating
      · abs_diff_per_lang  — |source − target| per shared language
        (small = similar rating = potential regularity)

Purpose:
  Test whether colexified concept pairs show similar ratings consistently
  across languages — i.e., is the rating regularity universal or language-specific?

Output:
  graphs/merged/<rating_type>.json   for each type
  graphs/merged/index.json           summary

Usage:
    uv run python case-studies/linking-datasets/merge_type_graphs.py
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
import csv
import io
import math
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

DATA_DIR    = Path(__file__).parent / "data"
GRAPHS_DIR  = Path(__file__).parent / "graphs"
NORARE_ZIP  = DATA_DIR / "norare-data.zip"
NORARE_TSV  = "norare-data/norare.tsv"
COLEX_JSON  = GRAPHS_DIR / "colexification_graph.json"
OUT_DIR     = GRAPHS_DIR / "merged"
OUT_DIR.mkdir(exist_ok=True)

RATING_TYPES = [
    "valence", "arousal", "dominance",
    "AoA", "imageability", "familiarity",
    "frequency", "concreteness", "emotionality",
]


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_colex_graph() -> dict:
    print(f"Loading colexification graph from {COLEX_JSON.name} ...")
    with COLEX_JSON.open(encoding="utf-8") as f:
        g = json.load(f)
    print(f"  {len(g['nodes'])} nodes,  {len(g['edges'])} edges")
    return g


def _canonical_columns(zip_path: Path, inner_tsv: str, numeric_types: set[str]) -> dict[tuple, dict]:
    """Read norare.tsv and return {(dataset, col_name): {type, lang}} keeping
    only the single canonical column per (dataset, rating_type) group:
      - If any column name contains '_MEAN', keep the shortest such column.
      - Otherwise keep the shortest column name (base form over _LOG, _PM, etc.).
    """
    all_rows: dict[tuple, dict] = {}
    per_ds_type: dict[tuple, list[str]] = defaultdict(list)

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_tsv) as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"):
                if row["NORARE"] in ("ratings", "norms") and row["TYPE"] in numeric_types:
                    key = (row["DATASET"], row["NAME"])
                    all_rows[key] = {"type": row["TYPE"], "lang": row["LANGUAGE"]}
                    per_ds_type[(row["DATASET"], row["TYPE"])].append(row["NAME"])

    keep: set[tuple] = set()
    for (ds, _rtype), cols in per_ds_type.items():
        if len(cols) == 1:
            keep.add((ds, cols[0]))
        else:
            mean_cols = [c for c in cols if "_MEAN" in c]
            chosen = min(mean_cols, key=len) if mean_cols else min(cols, key=len)
            keep.add((ds, chosen))

    return {k: v for k, v in all_rows.items() if k in keep}


def load_ratings_for_type(
    rating_type: str,
    var_meta: dict[tuple, dict],
) -> dict[str, dict[str, list[dict]]]:
    """Load ratings for one type directly from norare-data.zip dataset TSVs.

    Uses only the canonical column per (dataset, type) as selected by
    _canonical_columns(), avoiding wrong averages of MEAN/MIN/MAX or
    raw/log/PM frequency variants.

    Returns
    -------
    dict[concept_id -> dict[lang -> list[{value, dataset, column}]]]
    """
    ratings: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    # Group canonical columns by dataset for this type
    ds_cols: dict[str, tuple[str, str]] = {}   # ds_name -> (col_name, lang)
    for (ds, col), meta in var_meta.items():
        if meta["type"] == rating_type:
            ds_cols[ds] = (col, meta["lang"])

    if not ds_cols:
        return {}

    # First pass: collect raw values per dataset -> {cid: raw_value}
    ds_raw: dict[str, dict[str, float]] = {}   # ds_name -> {cid: raw_value}

    with zipfile.ZipFile(NORARE_ZIP) as zf:
        tsvs = [
            n for n in zf.namelist()
            if n.endswith(".tsv") and "/datasets/" in n
            and "raw" not in n and "-metadata" not in n
        ]
        for path in tsvs:
            ds_name = path.split("/")[2]
            if ds_name not in ds_cols:
                continue
            col_name, lang = ds_cols[ds_name]
            cid_vals: dict[str, float] = {}
            with zf.open(path) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
                )
                if not reader.fieldnames or "CONCEPTICON_ID" not in reader.fieldnames:
                    continue
                if col_name not in (reader.fieldnames or []):
                    continue
                for row in reader:
                    cid = row.get("CONCEPTICON_ID", "").strip()
                    if not cid:
                        continue
                    raw_val = row.get(col_name, "").strip()
                    try:
                        cid_vals[cid] = float(raw_val)
                    except (ValueError, TypeError):
                        continue
            if cid_vals:
                ds_raw[ds_name] = cid_vals

    # Second pass: z-score normalize within each dataset, then store
    for ds_name, cid_vals in ds_raw.items():
        col_name, lang = ds_cols[ds_name]
        vals = list(cid_vals.values())
        mean = sum(vals) / len(vals)
        std  = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        std  = std if std > 0 else 1.0

        for cid, raw_value in cid_vals.items():
            z = (raw_value - mean) / std
            ratings[cid][lang].append({
                "value":     raw_value,          # original scale (kept for reference)
                "z_score":   round(z, 6),        # within-dataset z-score
                "dataset":   ds_name,
                "column":    col_name,
                "ds_mean":   round(mean, 6),
                "ds_std":    round(std, 6),
            })

    return dict(ratings)


def mean_z_per_lang(
    raw: dict[str, list[dict]],
) -> dict[str, float]:
    """Average z-scores across datasets for each language.

    Each dataset is weighted equally regardless of size, since z-scoring
    already puts all datasets on a common scale (mean=0, std=1).
    """
    return {
        lang: round(sum(e["z_score"] for e in entries) / len(entries), 6)
        for lang, entries in raw.items()
    }


# ---------------------------------------------------------------------------
# Build merged graph for one rating type
# ---------------------------------------------------------------------------

def build_merged_graph(
    rating_type: str,
    ratings: dict[str, dict[str, list[dict]]],
    colex: dict,
) -> dict:
    """Merge rated concepts with colexification edges.

    Node inclusion: concept has ≥1 rating of this type in any language.
    Edge inclusion: colexification edge where both endpoints are rated.
    """
    colex_nodes = colex["nodes"]
    colex_edges = colex["edges"]

    rated_ids = set(ratings.keys())

    # --- Nodes ---
    nodes_out: dict[str, dict] = {}
    for cid in rated_ids:
        if cid not in colex_nodes:
            continue
        cn = colex_nodes[cid]
        # z-score averaged across datasets per language (scale-invariant)
        lang_z = mean_z_per_lang(ratings[cid])
        # raw provenance kept per entry
        lang_raw = {
            lang: [{"value": e["value"], "z_score": e["z_score"],
                    "dataset": e["dataset"], "column": e["column"]} for e in entries]
            for lang, entries in ratings[cid].items()
        }
        nodes_out[cid] = {
            "gloss":         cn["gloss"],
            "synset_id":     cn["synset_id"],
            "n_babel_langs": cn["n_babel_langs"],
            "languages":     cn["languages"],   # lemmas per BabelNet lang
            "ratings":       lang_raw,          # {lang: [{value, z_score, dataset, column}]}
            "mean_z":        lang_z,            # {lang: mean z-score across datasets}
        }

    # --- Edges (colexification edges between rated concepts) ---
    edges_out: list[dict] = []
    for edge in colex_edges:
        src, tgt = edge["source"], edge["target"]
        if src not in nodes_out or tgt not in nodes_out:
            continue

        src_z = nodes_out[src]["mean_z"]
        tgt_z = nodes_out[tgt]["mean_z"]

        # Languages where BOTH endpoints have a z-score
        langs_both = sorted(set(src_z) & set(tgt_z))

        edges_out.append({
            # Colexification provenance
            "source":           src,
            "target":           tgt,
            "n_languages":      edge["n_languages"],
            "n_instances":      edge["n_instances"],
            "colex_languages":  edge["languages"],
            "colexifications":  edge["colexifications"],

            # Z-scored ratings at each endpoint, per language
            "source_z":         src_z,
            "target_z":         tgt_z,

            # Languages where both endpoints have a z-score
            "langs_rated_both": langs_both,

            # |z_src - z_tgt| per shared language
            # Small value = concepts occupy similar position in their language's
            # rating distribution → cross-lingual regularity
            "abs_z_diff_per_lang": {
                lang: round(abs(src_z[lang] - tgt_z[lang]), 6)
                for lang in langs_both
            },
        })

    # Summary statistics for the metadata block
    n_colex_langs_with_ratings = len({
        lang
        for e in edges_out
        for lang in e["langs_rated_both"]
    })

    return {
        "metadata": {
            "rating_type":            rating_type,
            "n_nodes":                len(nodes_out),
            "n_edges":                len(edges_out),
            "rated_langs":            sorted({
                lang for n in nodes_out.values() for lang in n["mean_z"]
            }),
            "n_colex_langs_with_ratings": n_colex_langs_with_ratings,
            "contributing_datasets":  sorted({
                e["dataset"]
                for cid in ratings
                for lang_entries in ratings[cid].values()
                for e in lang_entries
            }),
            "note": (
                "mean_z is the z-score normalized rating averaged across datasets "
                "within each language. Z-scoring is done per-dataset (mean=0, std=1) "
                "before averaging, making ratings from different scales comparable."
            ),
        },
        "nodes": nodes_out,
        "edges": edges_out,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading canonical column metadata from norare.tsv ...")
    var_meta = _canonical_columns(NORARE_ZIP, NORARE_TSV, set(RATING_TYPES))
    print(f"  {len(var_meta)} canonical columns selected")

    colex = load_colex_graph()

    summary_index: dict[str, dict] = {}

    for rating_type in RATING_TYPES:
        ds_for_type = sorted({ds for (ds, _), m in var_meta.items() if m["type"] == rating_type})
        if not ds_for_type:
            print(f"\n[{rating_type}] No datasets — skipping")
            continue

        print(f"\n[{rating_type}]  {len(ds_for_type)} datasets ...")
        ratings = load_ratings_for_type(rating_type, var_meta)
        print(f"  {len(ratings)} concepts with ratings")

        graph = build_merged_graph(rating_type, ratings, colex)
        meta  = graph["metadata"]

        out_path = OUT_DIR / f"{rating_type}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
        size_mb = out_path.stat().st_size / 1_048_576

        print(f"  {meta['n_nodes']} nodes,  {meta['n_edges']} edges,  "
              f"{len(meta['rated_langs'])} rated langs  →  {out_path.name}  ({size_mb:.1f} MB)")

        summary_index[rating_type] = {
            "n_nodes":      meta["n_nodes"],
            "n_edges":      meta["n_edges"],
            "rated_langs":  meta["rated_langs"],
            "n_datasets":   len(ds_for_type),
            "datasets":     ds_for_type,
            "file":         out_path.name,
        }

    index_path = OUT_DIR / "index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(summary_index, f, ensure_ascii=False, indent=2)

    print(f"\nIndex written → {index_path}  ({len(summary_index)} types)")
    print("\nDone.")


if __name__ == "__main__":
    main()
