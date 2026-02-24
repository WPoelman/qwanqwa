"""
Cross-lingual Concept Graphs from NoRaRe + Concepticon

Pipeline
--------
1. Load numeric ratings (valence, arousal, AoA, frequency, …) for every
   concept from all norare-data dataset TSVs.
2. Link each concept to its Concepticon BabelNet synset (concepticon.zip),
   obtaining the set of languages that have a lemma for that concept.
3. Cross-lingual projection: a rating measured in one language (e.g. German
   valence) is projected to ALL languages that BabelNet lists for that
   concept — the concept is universal even if the rating was elicited in one
   language.
4. Build a full concept graph (nodes = concepts, edges = k-NN similarity on
   the rating vector, carrying the shared rating types and union of covered
   BabelNet languages).
5. Build per-language subgraphs (filter to concepts with a BabelNet lemma in
   that language) and compare.
6. Visualise and save to graphs/.

Usage
-----
    python case-studies/linking-datasets/concept_graph.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

csv.field_size_limit(sys.maxsize)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR   = Path(__file__).parent / "data"
NORARE_ZIP = DATA_DIR / "norare-data.zip"
NORARE_TSV = "norare-data/norare.tsv"          # variable-level metadata
CONCEPT_ZIP = DATA_DIR / "concepticon.zip"
CONCEPT_TSV = "concepticon_synsets/concepts_multilingual_senses.tsv"
OUT_DIR       = Path(__file__).parent / "graphs"
OUT_NORARE    = OUT_DIR / "norare"
OUT_DIR.mkdir(exist_ok=True)
OUT_NORARE.mkdir(exist_ok=True)

# Rating types we treat as numeric scalars (skip categorical / linguistic)
NUMERIC_TYPES = {
    "valence", "arousal", "dominance",
    "AoA", "imageability", "familiarity",
    "frequency", "concreteness", "emotionality",
}
RATING_TYPES = [          # fixed order → consistent feature vectors
    "valence", "arousal", "dominance",
    "AoA", "imageability", "familiarity",
    "frequency", "concreteness", "emotionality",
]

# Languages to build individual graphs for (BabelNet uppercase codes)
SHOWCASE_LANGS = ["EN", "DE", "FR", "ES", "ZH", "RU", "IT", "JA"]

K_NEIGHBORS = 6          # edges per node in the k-NN concept graph
MAX_NODES_PLOT = 300     # cap for legible visualisation


# ---------------------------------------------------------------------------
# 1. Load ratings from norare-data.zip
# ---------------------------------------------------------------------------

def load_variable_metadata(zip_path: Path, inner_tsv: str) -> dict[tuple, dict]:
    """Read norare.tsv; return {(dataset, col_name): {type, lang, category}}
    for numeric rating/norm columns only.

    When a dataset has multiple columns for the same rating type (e.g.
    SPANISH_AOA_MEAN, SPANISH_AOA_MIN, SPANISH_AOA_MAX), only the single
    canonical column is kept:
      1. Among columns whose name contains '_MEAN', keep the shortest one.
      2. If no '_MEAN' column exists, keep the shortest column name overall
         (e.g. SPANISH_FREQUENCY rather than SPANISH_FREQUENCY_LOG).
    This prevents averaging statistically incompatible columns (mean vs. min/max,
    raw count vs. log, pleasant vs. unpleasant, etc.).
    """
    all_rows: dict[tuple, dict] = {}
    per_ds_type: dict[tuple, list[str]] = defaultdict(list)

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_tsv) as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"):
                if row["NORARE"] in ("ratings", "norms") and row["TYPE"] in NUMERIC_TYPES:
                    key = (row["DATASET"], row["NAME"])
                    all_rows[key] = {
                        "type": row["TYPE"],
                        "lang": row["LANGUAGE"],
                        "category": row["NORARE"],
                    }
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


def load_ratings(zip_path: Path, var_meta: dict[tuple, dict]) -> dict[str, dict[str, list]]:
    """Scan every dataset TSV in the zip; collect numeric rating values.

    Returns
    -------
    dict[concept_id -> dict[rating_type -> list[{value, lang, dataset, column}]]]
      Each entry records the raw measured value together with the source
      language, dataset ID, and exact column name so provenance is fully
      preserved for downstream JSON export.
    """
    ratings: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    with zipfile.ZipFile(zip_path) as zf:
        tsvs = [
            n for n in zf.namelist()
            if (n.endswith(".tsv")
                and "/datasets/" in n
                and "raw" not in n
                and "-metadata" not in n)
        ]
        for path in tsvs:
            ds_name = path.split("/")[2]
            with zf.open(path) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
                )
                if not reader.fieldnames or "CONCEPTICON_ID" not in reader.fieldnames:
                    continue
                # columns that have variable metadata (numeric ratings)
                rated_cols = [
                    (col, var_meta[(ds_name, col)])
                    for col in (reader.fieldnames or [])
                    if (ds_name, col) in var_meta
                ]
                if not rated_cols:
                    continue
                for row in reader:
                    cid = row.get("CONCEPTICON_ID", "").strip()
                    if not cid:
                        continue
                    for col, meta in rated_cols:
                        raw_val = row.get(col, "").strip()
                        try:
                            value = float(raw_val)
                        except (ValueError, TypeError):
                            continue
                        ratings[cid][meta["type"]].append({
                            "value":   value,
                            "lang":    meta["lang"],
                            "dataset": ds_name,
                            "column":  col,
                        })
    return dict(ratings)


# ---------------------------------------------------------------------------
# 2. Load Concepticon synsets (concept → BabelNet languages + lemmas)
# ---------------------------------------------------------------------------

def load_concepticon(zip_path: Path, inner_tsv: str) -> dict[str, dict]:
    """Return dict[concept_id -> {gloss, synset_id, babel_langs, lemmas}]."""
    synsets: dict[str, dict] = {}
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_tsv) as raw:
            for row in csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
            ):
                cid  = row["concept_id"]
                lang = row["language"]
                lemma = row["lemma"].strip()
                if cid not in synsets:
                    synsets[cid] = {
                        "gloss": row["concept_gloss"],
                        "synset_id": row["synset_id"],
                        "babel_langs": set(),
                        "lemmas": defaultdict(list),
                    }
                synsets[cid]["babel_langs"].add(lang)
                if lemma:
                    synsets[cid]["lemmas"][lang].append(lemma)
    return synsets


# ---------------------------------------------------------------------------
# 3. Cross-lingual projection & rating vector construction
# ---------------------------------------------------------------------------

def build_concept_nodes(
    ratings: dict[str, dict[str, list]],
    concepticon: dict[str, dict],
) -> dict[str, dict]:
    """Merge NoRaRe ratings with Concepticon linkage.

    For each concept in both sources, compute:
      - mean rating per type (averaged across datasets / source languages)
      - projected_langs: the full set of BabelNet languages for this concept
        (cross-lingual projection: the rating, elicited in one language, is
        considered valid for any language in which the concept exists)

    Returns
    -------
    dict[concept_id -> {
        gloss, synset_id,
        babel_langs: set[str],
        lemmas: dict[lang -> list[str]],
        source_langs: dict[type -> list[str]],   # which languages rated it
        mean_ratings: dict[type -> float],        # averaged across sources
        projected_langs: set[str],                # = babel_langs (projection)
        n_rating_types: int,
    }]
    """
    nodes: dict[str, dict] = {}
    for cid in ratings:
        if cid not in concepticon:
            continue
        cs = concepticon[cid]
        rt = ratings[cid]
        mean_ratings = {t: float(np.mean([e["value"] for e in entries]))
                        for t, entries in rt.items()}
        source_langs = {t: sorted({e["lang"] for e in entries if e["lang"] and e["lang"] != "global"})
                        for t, entries in rt.items()}
        nodes[cid] = {
            "gloss":           cs["gloss"],
            "synset_id":       cs["synset_id"],
            "babel_langs":     cs["babel_langs"],
            "lemmas":          cs["lemmas"],
            "raw_ratings":     rt,          # full provenance kept for JSON export
            "source_langs":    source_langs,
            "mean_ratings":    mean_ratings,
            "projected_langs": cs["babel_langs"],
            "n_rating_types":  len(mean_ratings),
        }
    return nodes


def rating_matrix(
    nodes: dict[str, dict],
    min_types: int = 3,
) -> tuple[np.ndarray, list[str]]:
    """Build a (n_concepts × n_rating_types) feature matrix.

    Only includes concepts with at least *min_types* rating types.
    Frequency is log10-scaled; all columns are z-score normalised.

    Returns (matrix, ordered list of concept IDs).
    """
    eligible = [
        cid for cid, n in nodes.items()
        if n["n_rating_types"] >= min_types
    ]
    n = len(eligible)
    m = len(RATING_TYPES)
    X = np.full((n, m), np.nan)
    for i, cid in enumerate(eligible):
        for j, rt in enumerate(RATING_TYPES):
            val = nodes[cid]["mean_ratings"].get(rt)
            if val is not None:
                X[i, j] = np.log10(max(val, 1e-9)) if rt == "frequency" else val
    # Column-wise z-score (ignore NaN)
    col_mean = np.nanmean(X, axis=0)
    col_std  = np.nanstd(X, axis=0)
    col_std[col_std == 0] = 1.0
    X = (X - col_mean) / col_std
    X = np.nan_to_num(X, nan=0.0)   # fill remaining NaN with 0 (=mean)
    return X, eligible


# ---------------------------------------------------------------------------
# 4. Build graphs
# ---------------------------------------------------------------------------

def cosine_similarity_matrix(X: np.ndarray) -> np.ndarray:
    """Row-normalise X, return n×n cosine similarity matrix."""
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    Xn = X / norms
    return Xn @ Xn.T


def build_full_graph(
    X: np.ndarray,
    cids: list[str],
    nodes: dict[str, dict],
    k: int = K_NEIGHBORS,
) -> nx.Graph:
    """k-NN concept graph.

    Nodes carry all metadata from *nodes*.
    Edges carry:
      similarity      – cosine similarity of rating vectors
      shared_types    – rating types present in both endpoints
      union_langs     – union of BabelNet languages for the two concepts
    """
    sim = cosine_similarity_matrix(X)
    np.fill_diagonal(sim, -1)

    G = nx.Graph()
    for i, cid in enumerate(cids):
        n = nodes[cid]
        G.add_node(
            cid,
            gloss=n["gloss"],
            synset_id=n["synset_id"],
            n_langs=len(n["babel_langs"]),
            n_rating_types=n["n_rating_types"],
            **{f"rating_{t}": n["mean_ratings"].get(t, float("nan"))
               for t in RATING_TYPES},
        )

    for i, cid_i in enumerate(cids):
        top_k = np.argsort(sim[i])[::-1][:k]
        for j in top_k:
            if j <= i:
                continue
            cid_j = cids[j]
            shared = sorted(
                nodes[cid_i]["mean_ratings"].keys()
                & nodes[cid_j]["mean_ratings"].keys()
            )
            union_langs = nodes[cid_i]["babel_langs"] | nodes[cid_j]["babel_langs"]
            G.add_edge(
                cid_i, cid_j,
                similarity=float(sim[i, j]),
                shared_types=shared,
                n_shared_types=len(shared),
                union_langs=union_langs,
                n_union_langs=len(union_langs),
            )
    return G


def build_language_graph(
    G_full: nx.Graph,
    lang: str,                      # BabelNet uppercase code, e.g. "EN"
    nodes: dict[str, dict],
) -> nx.Graph:
    """Subgraph of *G_full* restricted to concepts with a BabelNet lemma in *lang*.

    Each node additionally gets:
      lemma_in_lang  – first BabelNet lemma for this language (or concept gloss)
    """
    keep = {
        cid for cid in G_full.nodes
        if lang in nodes[cid]["babel_langs"]
    }
    H = G_full.subgraph(keep).copy()
    for cid in H.nodes:
        lemmas = nodes[cid]["lemmas"].get(lang, [])
        H.nodes[cid]["lemma_in_lang"] = lemmas[0] if lemmas else nodes[cid]["gloss"]
    return H


# ---------------------------------------------------------------------------
# 5. Visualisation helpers
# ---------------------------------------------------------------------------

def _draw_graph(
    G: nx.Graph,
    ax: plt.Axes,
    title: str,
    color_attr: str = "rating_valence",
    label_attr: str = "gloss",
    max_nodes: int = MAX_NODES_PLOT,
    seed: int = 42,
) -> None:
    """Draw graph on *ax*; cap to *max_nodes* highest-degree nodes."""
    if len(G) == 0:
        ax.set_title(f"{title}\n(no data)")
        ax.axis("off")
        return

    # Subsample to *max_nodes* highest-degree nodes for legibility
    if len(G) > max_nodes:
        top = sorted(G.degree, key=lambda x: x[1], reverse=True)[:max_nodes]
        G = G.subgraph([n for n, _ in top]).copy()

    pos = nx.spring_layout(G, seed=seed, k=0.6)

    # Node colour by rating attribute (NaN → grey)
    raw_vals = np.array([G.nodes[n].get(color_attr, np.nan) for n in G.nodes])
    finite   = raw_vals[np.isfinite(raw_vals)]
    if finite.size > 0:
        vmin, vmax = finite.min(), finite.max()
        normed = np.where(np.isfinite(raw_vals), (raw_vals - vmin) / max(vmax - vmin, 1e-9), 0.5)
        colors = plt.cm.RdYlGn(normed)
    else:
        colors = ["#aaaaaa"] * len(G)

    # Node size by language coverage
    sizes = [20 + 0.3 * G.nodes[n].get("n_langs", 0) for n in G.nodes]

    # Edge width by similarity
    edge_sims = [G[u][v].get("similarity", 0.5) for u, v in G.edges]
    edge_widths = [0.3 + 2.5 * max(0, s) for s in edge_sims]

    nx.draw_networkx_edges(G, pos, ax=ax, width=edge_widths, alpha=0.25, edge_color="#555555")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=sizes, node_color=colors, alpha=0.85)

    # Labels only for high-degree nodes (avoid clutter)
    degree_threshold = max(1, np.percentile(list(dict(G.degree()).values()), 80))
    label_nodes = {n: G.nodes[n].get(label_attr, n)
                   for n, d in G.degree() if d >= degree_threshold}
    nx.draw_networkx_labels(G, pos, labels=label_nodes, ax=ax, font_size=5.5, font_weight="bold")

    ax.set_title(title, fontsize=9, pad=4)
    ax.axis("off")


def plot_full_graph(G: nx.Graph, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    for ax, attr, label in zip(
        axes,
        ["rating_valence", "rating_arousal", "rating_AoA"],
        ["Valence", "Arousal", "AoA (age of acquisition)"],
    ):
        _draw_graph(G, ax, f"Concept graph — coloured by {label}", color_attr=attr)
    sm = plt.cm.ScalarMappable(cmap="RdYlGn")
    sm.set_array([])
    fig.colorbar(sm, ax=axes, fraction=0.02, pad=0.01, label="low → high rating")
    fig.suptitle(
        f"Full cross-lingual concept graph  ({len(G)} nodes, {G.number_of_edges()} edges)\n"
        "Nodes = Concepticon concepts  |  Edges = k-NN cosine similarity on rating vectors  |"
        "  Node size ∝ BabelNet language coverage",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


def plot_language_comparison(
    lang_graphs: dict[str, nx.Graph],
    nodes: dict[str, dict],
    out_path: Path,
) -> None:
    langs = [l for l in SHOWCASE_LANGS if l in lang_graphs and len(lang_graphs[l]) > 0]
    n = len(langs)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5, rows * 5))
    axes = np.array(axes).flatten()
    for i, lang in enumerate(langs):
        H = lang_graphs[lang]
        n_concepts = len(H)
        _draw_graph(
            H, axes[i],
            title=f"{lang}  ({n_concepts} concepts)",
            color_attr="rating_valence",
            label_attr="lemma_in_lang",
            seed=42,
        )
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
    fig.suptitle(
        "Per-language concept subgraphs\n"
        "Nodes = concepts with a BabelNet lemma in that language  |"
        "  Coloured by valence  |  Labels = language-specific lemma",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


def plot_language_size_comparison(
    lang_graphs: dict[str, nx.Graph],
    out_path: Path,
) -> None:
    """Bar chart: node count per language."""
    data = {l: len(G) for l, G in lang_graphs.items() if len(G) > 0}
    data = dict(sorted(data.items(), key=lambda x: -x[1]))
    fig, ax = plt.subplots(figsize=(14, 4))
    bars = ax.bar(list(data.keys()), list(data.values()), color="steelblue", edgecolor="white")
    ax.set_xlabel("BabelNet language code")
    ax.set_ylabel("Concepts with rated + BabelNet entry")
    ax.set_title("Concept coverage per language after cross-lingual projection")
    ax.bar_label(bars, padding=2, fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


# ---------------------------------------------------------------------------
# 6. Stats helpers
# ---------------------------------------------------------------------------

def print_projection_stats(nodes: dict[str, dict]) -> None:
    """Report cross-lingual projection reach per rating type."""
    from collections import defaultdict
    type_langs: dict[str, set] = defaultdict(set)
    type_projected: dict[str, list] = defaultdict(list)
    for n in nodes.values():
        for rt in n["mean_ratings"]:
            for sl in n["source_langs"].get(rt, []):
                type_langs[rt].add(sl)
            type_projected[rt].append(len(n["projected_langs"]))
    print()
    print("  Cross-lingual projection summary")
    print(f"  {'Rating type':<16} {'Source langs':>12}  {'Avg projected langs':>20}  {'Max projected':>14}")
    print("  " + "-" * 68)
    for rt in RATING_TYPES:
        if rt not in type_langs:
            continue
        avg_proj = np.mean(type_projected[rt]) if type_projected[rt] else 0
        max_proj = max(type_projected[rt]) if type_projected[rt] else 0
        print(
            f"  {rt:<16} {len(type_langs[rt]):>12}  {avg_proj:>20.1f}  {max_proj:>14}"
        )


# ---------------------------------------------------------------------------
# 7. JSON export
# ---------------------------------------------------------------------------

def export_json(
    G: nx.Graph,
    nodes: dict[str, dict],
    out_path: Path,
) -> None:
    """Serialise the concept graph to a self-contained JSON file.

    Schema
    ------
    {
      "metadata": { n_nodes, n_edges, rating_types, ... },
      "nodes": {
        "<concepticon_id>": {
          "gloss":      str,          // Concepticon concept name
          "synset_id":  str,          // BabelNet synset identifier
          "n_babel_langs": int,       // number of BabelNet language entries
          "languages": {              // from Concepticon BabelNet synsets
            "<LANG_CODE>": ["lemma1", "lemma2", ...]
          },
          "ratings": {               // from NoRaRe datasets
            "<type>": [              // e.g. "valence", "arousal", "AoA", ...
              {
                "value":   float,
                "lang":    str,      // ISO 639-1/3 source language
                "dataset": str,      // norare-data dataset ID
                "column":  str       // exact TSV column name
              }, ...
            ]
          },
          "mean_ratings": { "<type>": float }  // mean across all measurements
        }
      },
      "edges": [
        {
          "source":      str,         // concepticon_id
          "target":      str,         // concepticon_id
          "similarity":  float,       // cosine similarity of rating vectors
          "shared_rating_types": [str, ...],
          "n_shared_types": int,
          "ratings": {                // per shared type: values at each endpoint
            "<type>": {
              "source_mean":     float,
              "target_mean":     float,
              "source_datasets": [str, ...],
              "target_datasets": [str, ...],
              "source_langs":    [str, ...],
              "target_langs":    [str, ...]
            }
          },
          "union_babel_langs":  [str, ...],  // sorted union of BabelNet langs
          "n_union_langs": int
        }, ...
      ]
    }
    """
    doc: dict = {
        "metadata": {
            "n_nodes":      len(G),
            "n_edges":      G.number_of_edges(),
            "rating_types": RATING_TYPES,
            "k_neighbors":  K_NEIGHBORS,
            "source_norare": str(NORARE_ZIP.name),
            "source_concepticon": str(CONCEPT_ZIP.name),
        },
        "nodes": {},
        "edges": [],
    }

    # --- nodes ---
    for cid in G.nodes:
        n = nodes[cid]
        # Deduplicate lemmas per language (BabelNet repeats many entries),
        # preserve insertion order, cap at 5 per language.
        deduped_langs: dict[str, list[str]] = {}
        for lang, lemmas in sorted(n["lemmas"].items()):
            seen: list[str] = []
            for lem in lemmas:
                if lem not in seen:
                    seen.append(lem)
                if len(seen) == 5:
                    break
            deduped_langs[lang] = seen

        doc["nodes"][cid] = {
            "gloss":         n["gloss"],
            "synset_id":     n["synset_id"],
            "n_babel_langs": len(n["babel_langs"]),
            "languages":     deduped_langs,
            "ratings":       n["raw_ratings"],   # full provenance
            "mean_ratings":  {
                t: round(v, 6) for t, v in n["mean_ratings"].items()
            },
        }

    # --- edges ---
    for src, tgt, edata in G.edges(data=True):
        src_node = nodes[src]
        tgt_node = nodes[tgt]

        rating_detail: dict[str, dict] = {}
        for rtype in edata.get("shared_types", []):
            src_entries = src_node["raw_ratings"].get(rtype, [])
            tgt_entries = tgt_node["raw_ratings"].get(rtype, [])
            rating_detail[rtype] = {
                "source_mean":     round(src_node["mean_ratings"].get(rtype, float("nan")), 6),
                "target_mean":     round(tgt_node["mean_ratings"].get(rtype, float("nan")), 6),
                "source_datasets": sorted({e["dataset"] for e in src_entries}),
                "target_datasets": sorted({e["dataset"] for e in tgt_entries}),
                "source_langs":    sorted({e["lang"] for e in src_entries if e["lang"] != "global"}),
                "target_langs":    sorted({e["lang"] for e in tgt_entries if e["lang"] != "global"}),
            }

        doc["edges"].append({
            "source":              src,
            "target":              tgt,
            "similarity":          round(edata["similarity"], 6),
            "shared_rating_types": edata.get("shared_types", []),
            "n_shared_types":      edata.get("n_shared_types", 0),
            "ratings":             rating_detail,
            "union_babel_langs":   sorted(edata.get("union_langs", set())),
            "n_union_langs":       edata.get("n_union_langs", 0),
        })

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  Saved → {out_path.name}  ({size_mb:.1f} MB, "
          f"{len(doc['nodes'])} nodes, {len(doc['edges'])} edges)")


# ---------------------------------------------------------------------------
# 8. Per-dataset graphs
# ---------------------------------------------------------------------------

def _dataset_types_ordered(ds_name: str, var_meta: dict[tuple, dict]) -> list[str]:
    """Return rating types for *ds_name* in RATING_TYPES order."""
    ds_types = {meta["type"] for (ds, _), meta in var_meta.items() if ds == ds_name}
    return [t for t in RATING_TYPES if t in ds_types]


def _filter_ratings_to_dataset(
    ratings: dict[str, dict[str, list]],
    ds_name: str,
) -> dict[str, dict[str, list]]:
    """Return a ratings sub-dict containing only entries from *ds_name*."""
    out: dict[str, dict[str, list]] = {}
    for cid, types in ratings.items():
        filtered = {
            rtype: [e for e in entries if e["dataset"] == ds_name]
            for rtype, entries in types.items()
        }
        filtered = {t: v for t, v in filtered.items() if v}
        if filtered:
            out[cid] = filtered
    return out


def build_dataset_graph(
    ds_name: str,
    ds_ratings: dict[str, dict[str, list]],
    ds_types: list[str],
    concepticon: dict[str, dict],
    k: int = K_NEIGHBORS,
) -> tuple[nx.Graph | None, dict[str, dict]]:
    """Build a k-NN concept graph for a single norare dataset.

    Returns (None, {}) if the dataset has too few concepts to be useful.
    """
    # Nodes: intersection of this dataset's concepts and Concepticon
    nodes = build_concept_nodes(ds_ratings, concepticon)
    if len(nodes) < max(k + 1, 3):
        return None, {}

    # Rating matrix using only this dataset's types
    n = len(nodes)
    cids = sorted(nodes.keys())
    m = len(ds_types)
    if m == 0:
        return None, {}

    X = np.full((n, m), np.nan)
    for i, cid in enumerate(cids):
        for j, rtype in enumerate(ds_types):
            val = nodes[cid]["mean_ratings"].get(rtype)
            if val is not None:
                X[i, j] = np.log10(max(val, 1e-9)) if rtype == "frequency" else val

    col_mean = np.nanmean(X, axis=0)
    col_std  = np.nanstd(X, axis=0)
    col_std[col_std == 0] = 1.0
    X = (X - col_mean) / col_std
    X = np.nan_to_num(X, nan=0.0)

    k_actual = min(k, len(cids) - 1)
    G = build_full_graph(X, cids, nodes, k=k_actual)
    return G, nodes


def export_dataset_json(
    G: nx.Graph,
    nodes: dict[str, dict],
    ds_name: str,
    ds_types: list[str],
    ds_langs: list[str],
    out_path: Path,
) -> None:
    """Export a single-dataset concept graph to JSON.

    Schema mirrors export_json() but scoped to one dataset:
      metadata  – dataset name, rating types, source languages, counts
      nodes     – {concept_id: {gloss, synset_id, n_babel_langs, languages,
                                ratings (this dataset only), mean_ratings}}
      edges     – k-NN edges with similarity, shared rating types, rating
                  values at each endpoint, and union BabelNet languages
    """
    doc: dict = {
        "metadata": {
            "dataset":       ds_name,
            "rating_types":  ds_types,
            "source_langs":  ds_langs,
            "n_nodes":       len(G),
            "n_edges":       G.number_of_edges(),
            "k_neighbors":   K_NEIGHBORS,
            "source_norare": NORARE_ZIP.name,
            "source_concepticon": CONCEPT_ZIP.name,
        },
        "nodes": {},
        "edges": [],
    }

    for cid in G.nodes:
        n = nodes[cid]
        # Deduplicate lemmas (cap at 5 per language)
        deduped: dict[str, list[str]] = {}
        for lang, lemmas in sorted(n["lemmas"].items()):
            seen: list[str] = []
            for lem in lemmas:
                if lem not in seen:
                    seen.append(lem)
                if len(seen) == 5:
                    break
            deduped[lang] = seen

        doc["nodes"][cid] = {
            "gloss":         n["gloss"],
            "synset_id":     n["synset_id"],
            "n_babel_langs": len(n["babel_langs"]),
            "languages":     deduped,
            "ratings":       n["raw_ratings"],
            "mean_ratings":  {t: round(v, 6) for t, v in n["mean_ratings"].items()},
        }

    for src, tgt, edata in G.edges(data=True):
        src_node = nodes[src]
        tgt_node = nodes[tgt]
        rating_detail: dict[str, dict] = {}
        for rtype in edata.get("shared_types", []):
            src_entries = src_node["raw_ratings"].get(rtype, [])
            tgt_entries = tgt_node["raw_ratings"].get(rtype, [])
            rating_detail[rtype] = {
                "source_mean":  round(src_node["mean_ratings"].get(rtype, float("nan")), 6),
                "target_mean":  round(tgt_node["mean_ratings"].get(rtype, float("nan")), 6),
                "source_langs": sorted({e["lang"] for e in src_entries if e["lang"] != "global"}),
                "target_langs": sorted({e["lang"] for e in tgt_entries if e["lang"] != "global"}),
            }
        doc["edges"].append({
            "source":              src,
            "target":              tgt,
            "similarity":          round(edata["similarity"], 6),
            "shared_rating_types": edata.get("shared_types", []),
            "ratings":             rating_detail,
            "union_babel_langs":   sorted(edata.get("union_langs", set())),
            "n_union_langs":       edata.get("n_union_langs", 0),
        })

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"    {ds_name:<45} {len(G):>5} nodes  {G.number_of_edges():>6} edges  {size_mb:.1f} MB")


def run_per_dataset_export(
    ratings: dict[str, dict[str, list]],
    concepticon: dict[str, dict],
    var_meta: dict[tuple, dict],
    out_dir: Path,
) -> dict[str, dict]:
    """Build and export one JSON graph per norare dataset.

    Returns an index dict {ds_name -> {n_nodes, n_edges, rating_types, langs}}
    for writing a summary index file.
    """
    # Collect all dataset names that have numeric ratings
    ds_names = sorted({ds for ds, _ in var_meta})

    index: dict[str, dict] = {}
    print(f"  {'Dataset':<45} {'Nodes':>5}  {'Edges':>6}  Size")
    print("  " + "-" * 72)

    for ds_name in ds_names:
        ds_types = _dataset_types_ordered(ds_name, var_meta)
        ds_langs = sorted({
            meta["lang"]
            for (ds, _), meta in var_meta.items()
            if ds == ds_name and meta["lang"] not in ("global", "")
        })
        ds_ratings = _filter_ratings_to_dataset(ratings, ds_name)

        G, nodes = build_dataset_graph(ds_name, ds_ratings, ds_types, concepticon)
        if G is None:
            print(f"    {ds_name:<45} (skipped — too few concepts)")
            continue

        out_path = out_dir / f"{ds_name}.json"
        export_dataset_json(G, nodes, ds_name, ds_types, ds_langs, out_path)
        index[ds_name] = {
            "n_nodes":      len(G),
            "n_edges":      G.number_of_edges(),
            "rating_types": ds_types,
            "source_langs": ds_langs,
            "file":         out_path.name,
        }

    return index


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # 1. Variable metadata
    print("Loading variable metadata from norare.tsv...")
    var_meta = load_variable_metadata(NORARE_ZIP, NORARE_TSV)
    print(f"  {len(var_meta)} numeric rating/norm variables")

    # 2. Ratings from dataset TSVs
    print("Loading ratings from dataset TSVs...")
    ratings = load_ratings(NORARE_ZIP, var_meta)
    print(f"  {len(ratings)} concepts have at least one numeric rating")

    # 3. Concepticon synsets
    print(f"Loading Concepticon synsets from {CONCEPT_ZIP.name}...")
    concepticon = load_concepticon(CONCEPT_ZIP, CONCEPT_TSV)
    print(f"  {len(concepticon)} concepts loaded")

    # 4. Build linked concept nodes (cross-lingual projection)
    print("Linking NoRaRe ratings to Concepticon (cross-lingual projection)...")
    nodes = build_concept_nodes(ratings, concepticon)
    print(f"  {len(nodes)} concepts linked  (rated in NoRaRe + in Concepticon)")
    print_projection_stats(nodes)

    # 5. Rating matrix & k-NN graph
    print(f"\nBuilding rating matrix (min 3 rating types)...")
    X, cids = rating_matrix(nodes, min_types=3)
    print(f"  Matrix shape: {X.shape}  ({X.shape[0]} concepts × {X.shape[1]} rating types)")

    print(f"Building full k-NN concept graph (k={K_NEIGHBORS})...")
    G_full = build_full_graph(X, cids, nodes, k=K_NEIGHBORS)
    print(f"  Graph: {len(G_full)} nodes, {G_full.number_of_edges()} edges")

    # 6. Per-language subgraphs
    print("\nBuilding per-language subgraphs...")
    lang_graphs: dict[str, nx.Graph] = {}
    all_langs = sorted({lang for cid in cids for lang in nodes[cid]["babel_langs"]})
    for lang in all_langs:
        H = build_language_graph(G_full, lang, nodes)
        lang_graphs[lang] = H

    # Summary table: top-20 languages by concept coverage
    lang_sizes = sorted(lang_graphs.items(), key=lambda x: -len(x[1]))
    print(f"  {'Lang':<6}  {'Concepts':>8}  {'Edges':>8}")
    for lang, H in lang_sizes[:20]:
        print(f"  {lang:<6}  {len(H):>8}  {H.number_of_edges():>8}")

    # 7. Visualisation
    print("\nSaving graphs to", OUT_DIR, "...")

    print("  Plotting full cross-lingual concept graph...")
    plot_full_graph(G_full, OUT_DIR / "concept_graph_full.png")

    print("  Plotting per-language comparison...")
    plot_language_comparison(lang_graphs, nodes, OUT_DIR / "concept_graph_by_language.png")

    print("  Plotting language coverage bar chart...")
    plot_language_size_comparison(lang_graphs, OUT_DIR / "language_coverage.png")

    # 8. Per-dataset JSON export → graphs/norare/
    print(f"\nExporting per-dataset graphs to {OUT_NORARE} ...")
    ds_index = run_per_dataset_export(ratings, concepticon, var_meta, OUT_NORARE)

    # Write index file
    index_path = OUT_NORARE / "index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(ds_index, f, ensure_ascii=False, indent=2)
    print(f"\n  Index written → {index_path.name}  ({len(ds_index)} datasets)")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
