"""
Cross-lingual Colexification Graph from Concepticon BabelNet Synsets

A colexification occurs when two distinct concepts are expressed by the
same word/lemma in the same language.  This script builds a graph where:

  Nodes = Concepticon concept sets (concept_id, gloss, BabelNet info)
  Edges = colexification events: the two concepts share at least one
          lemma in at least one language.

Edge attributes
---------------
  colexifications  list of {"language", "lemma", "n_concepts_for_lemma"}
                   one entry per (lang, lemma) pair that links the two
                   concepts; n_concepts_for_lemma is how many concepts
                   that lemma covers in that language (polysemy count).
  languages        sorted list of language codes where the colex. occurs
  n_languages      number of distinct languages
  n_instances      total number of (lang, lemma) pairs driving the edge

Source filtering
----------------
Only lemmas from linguistic databases are used (Open Multilingual Wordnet,
Wiktionary, Multilingual Central Repository, Princeton WordNet, Open English
WordNet, SlowNet, IceWordNet, WordNet translations).  Wikipedia article
titles are excluded via two heuristics:
  1. Lemmas containing underscores are dropped (Wikipedia uses underscores
     for spaces in article titles).
  2. Only sources in LING_SOURCES are considered.
Additionally, (lang, lemma) pairs that map to more than MAX_POLYSEMY
concepts are dropped — these are function words / light verbs whose
high polysemy is an artefact of wordnet-sense granularity, not a
meaningful colexification pattern.

Usage
-----
    python case-studies/linking-datasets/colexification_graph.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import networkx as nx
import numpy as np

csv.field_size_limit(sys.maxsize)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
DATA_DIR     = Path(__file__).parent / "data"
CONCEPT_ZIP  = DATA_DIR / "concepticon.zip"
CONCEPT_TSV  = "concepticon_synsets/concepts_multilingual_senses.tsv"
OUT_DIR      = Path(__file__).parent / "graphs"
OUT_DIR.mkdir(exist_ok=True)

# Linguistic data sources (exclude Wikipedia, Wikidata, etc.)
LING_SOURCES = {"OMWN", "WIKT", "MCR", "WN", "OEWN", "SLOWNET", "ICEWN", "WNTR"}

# Drop (lang, lemma) pairs that cover more than this many concepts:
# removes grammatical function words whose high polysemy is not informative.
#
# ┌──────────────┬──────────────┐
# │ max_polysemy │ Unique
# edges │
# ├──────────────┼──────────────┤
# │ 5            │ 56, 064       │
# ├──────────────┼──────────────┤
# │ 8            │ 97, 523       │
# ├──────────────┼──────────────┤
# │ 10           │ 118, 034      │
# ├──────────────┼──────────────┤
# │ 15           │ 151, 306      │
# ├──────────────┼──────────────┤
# │ 20           │ 170, 405      │
# └──────────────┴──────────────┘

MAX_POLYSEMY = 5


# ---------------------------------------------------------------------------
# 1. Load BabelNet data: concept metadata + (lang, lemma) → concepts index
# ---------------------------------------------------------------------------

def load_babelnet(
    zip_path: Path,
    inner_tsv: str,
) -> tuple[dict[str, dict], dict[tuple[str, str], list[tuple[str, str]]]]:
    """Read the BabelNet synsets TSV in one pass.

    Returns
    -------
    concepts : dict[concept_id -> {gloss, synset_id, n_babel_langs, lemmas}]
               lemmas is dict[lang -> list[original_lemma]] (only clean entries)
    index    : dict[(lang, lemma_lower) -> list[(concept_id, original_lemma)]]
               only linguistic sources, no underscores in lemma
    """
    concepts: dict[str, dict] = {}
    index: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(inner_tsv) as raw:
            for row in csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8"), delimiter="\t"
            ):
                cid   = row["concept_id"]
                lang  = row["language"]
                lemma = row["lemma"].strip()
                src   = row["source"].split("_")[0]

                # ---- concept metadata (all rows) ----
                if cid not in concepts:
                    concepts[cid] = {
                        "gloss":      row["concept_gloss"],
                        "synset_id":  row["synset_id"],
                        "babel_langs": set(),
                        "lemmas":     defaultdict(list),
                    }
                concepts[cid]["babel_langs"].add(lang)

                if not lemma:
                    continue

                # Store clean lemmas for node output (deduplicated, max 5)
                lang_lemmas = concepts[cid]["lemmas"][lang]
                if lemma not in lang_lemmas and len(lang_lemmas) < 5:
                    lang_lemmas.append(lemma)

                # ---- colexification index (filtered rows only) ----
                if "_" in lemma:
                    continue   # Wikipedia article title heuristic
                if src not in LING_SOURCES:
                    continue
                index[(lang, lemma.lower())].append((cid, lemma))

    # Convert babel_langs sets to counts
    for info in concepts.values():
        info["n_babel_langs"] = len(info.pop("babel_langs"))
        info["lemmas"] = dict(info["lemmas"])

    return concepts, dict(index)


# ---------------------------------------------------------------------------
# 2. Build colexification graph
# ---------------------------------------------------------------------------

def build_colexification_graph(
    concepts: dict[str, dict],
    index: dict[tuple[str, str], list[tuple[str, str]]],
    max_polysemy: int = MAX_POLYSEMY,
) -> nx.Graph:
    """Build the colexification graph.

    For every (lang, lemma) pair in *index* that links 2..max_polysemy
    distinct concepts, add/update edges between all pairs of those concepts.

    Edge data accumulated:
      colexifications  list of {language, lemma, n_concepts_for_lemma}
      language_set     set of languages (internal; converted to list on finish)
    """
    G = nx.Graph()

    # Add all concept nodes
    for cid, info in concepts.items():
        G.add_node(
            cid,
            gloss=info["gloss"],
            synset_id=info["synset_id"],
            n_babel_langs=info["n_babel_langs"],
        )

    # Accumulate colexification edges
    for (lang, lem_lower), entries in index.items():
        # Deduplicate: keep unique concept_ids only
        seen_cids: dict[str, str] = {}   # cid -> first original lemma seen
        for cid, orig_lemma in entries:
            if cid not in seen_cids:
                seen_cids[cid] = orig_lemma

        if len(seen_cids) < 2 or len(seen_cids) > max_polysemy:
            continue

        colex_entry = {
            "language": lang,
            "lemma":    next(iter(seen_cids.values())),   # representative form
            "n_concepts_for_lemma": len(seen_cids),
        }

        for cid_a, cid_b in combinations(sorted(seen_cids), 2):
            if G.has_edge(cid_a, cid_b):
                G[cid_a][cid_b]["colexifications"].append(colex_entry)
                G[cid_a][cid_b]["language_set"].add(lang)
            else:
                G.add_edge(
                    cid_a, cid_b,
                    colexifications=[colex_entry],
                    language_set={lang},
                )

    # Finalise edge attributes
    for u, v, data in G.edges(data=True):
        data["languages"]   = sorted(data.pop("language_set"))
        data["n_languages"] = len(data["languages"])
        data["n_instances"] = len(data["colexifications"])

    return G


# ---------------------------------------------------------------------------
# 3. JSON export
# ---------------------------------------------------------------------------

def export_json(G: nx.Graph, concepts: dict[str, dict], out_path: Path) -> None:
    """Write the full graph to a self-contained JSON file.

    Schema
    ------
    {
      "metadata": { ... },
      "nodes": {
        "<id>": {
          "gloss": str,
          "synset_id": str,
          "n_babel_langs": int,
          "languages": { "<LANG>": ["lemma1", ...] }   // from Concepticon
        }
      },
      "edges": [
        {
          "source": str,           // concept_id
          "target": str,           // concept_id
          "n_languages": int,      // how many languages colexify these two
          "n_instances": int,      // total (lang, lemma) pairs driving the edge
          "languages": [str, ...], // sorted list of language codes
          "colexifications": [
            {
              "language": str,
              "lemma":    str,              // the shared word form
              "n_concepts_for_lemma": int   // polysemy count for this (lang,lemma)
            }, ...
          ]
        }, ...
      ]
    }
    """
    doc: dict = {
        "metadata": {
            "n_nodes":        len(G),
            "n_edges":        G.number_of_edges(),
            "source":         CONCEPT_ZIP.name,
            "ling_sources":   sorted(LING_SOURCES),
            "max_polysemy":   MAX_POLYSEMY,
            "description": (
                "Cross-lingual colexification graph. "
                "Two concepts share an edge when they are expressed by the "
                "same lemma in the same language in at least one BabelNet "
                "linguistic source."
            ),
        },
        "nodes": {},
        "edges": [],
    }

    for cid in G.nodes:
        info = concepts[cid]
        doc["nodes"][cid] = {
            "gloss":        info["gloss"],
            "synset_id":    info["synset_id"],
            "n_babel_langs": info["n_babel_langs"],
            "languages":    info["lemmas"],
        }

    for src, tgt, edata in G.edges(data=True):
        doc["edges"].append({
            "source":          src,
            "target":          tgt,
            "n_languages":     edata["n_languages"],
            "n_instances":     edata["n_instances"],
            "languages":       edata["languages"],
            "colexifications": edata["colexifications"],
        })

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  Saved → {out_path.name}  ({size_mb:.1f} MB, "
          f"{len(doc['nodes'])} nodes, {len(doc['edges'])} edges)")


# ---------------------------------------------------------------------------
# 4. Visualisation
# ---------------------------------------------------------------------------

def plot_colexification_graph(
    G: nx.Graph,
    concepts: dict[str, dict],
    out_path: Path,
    max_nodes: int = 400,
    seed: int = 42,
) -> None:
    """Visualise the largest connected component of the colexification graph.

    Node size   ∝ degree (number of distinct concepts it colexifies with)
    Node colour = number of languages in which colexifications occur (summed
                  over all edges, i.e. weighted degree by language count)
    Edge width  ∝ n_languages (cross-lingual strength of colexification)
    Labels      = concept gloss, shown for high-degree nodes only
    """
    # Largest connected component
    gcc = max(nx.connected_components(G), key=len)
    H = G.subgraph(gcc).copy()

    # Subsample to max_nodes highest-degree nodes
    if len(H) > max_nodes:
        top = sorted(H.degree, key=lambda x: x[1], reverse=True)[:max_nodes]
        H = H.subgraph([n for n, _ in top]).copy()

    pos = nx.spring_layout(H, seed=seed, k=1.2, iterations=60)

    # Node colour = sum of n_languages over all edges (cross-lingual reach)
    lang_reach = defaultdict(int)
    for u, v, d in H.edges(data=True):
        lang_reach[u] += d["n_languages"]
        lang_reach[v] += d["n_languages"]
    reach_vals = np.array([lang_reach[n] for n in H.nodes], dtype=float)
    if reach_vals.max() > 0:
        normed = reach_vals / reach_vals.max()
    else:
        normed = np.zeros_like(reach_vals)
    node_colors = plt.cm.plasma(normed)

    # Node size ∝ degree
    degrees = dict(H.degree())
    node_sizes = [30 + 15 * degrees[n] for n in H.nodes]

    # Edge width & alpha ∝ n_languages
    edge_n_langs = [d["n_languages"] for _, _, d in H.edges(data=True)]
    max_nl = max(edge_n_langs) if edge_n_langs else 1
    edge_widths = [0.3 + 3.0 * (nl / max_nl) for nl in edge_n_langs]
    edge_alphas = [0.15 + 0.6 * (nl / max_nl) for nl in edge_n_langs]

    fig, ax = plt.subplots(figsize=(18, 16))

    # Draw edges with per-edge alpha (drawn individually for alpha support)
    edges_list = list(H.edges(data=True))
    for (u, v, d), w, a in zip(edges_list, edge_widths, edge_alphas):
        nx.draw_networkx_edges(
            H, pos, edgelist=[(u, v)], ax=ax, width=w, alpha=a,
            edge_color="#444466",
        )

    nx.draw_networkx_nodes(
        H, pos, ax=ax,
        node_size=node_sizes,
        node_color=node_colors,
        linewidths=0.3,
        edgecolors="#222222",
    )

    # Labels for top-degree nodes
    deg_threshold = np.percentile(list(degrees.values()), 85)
    labels = {
        n: concepts[n]["gloss"]
        for n in H.nodes if degrees[n] >= deg_threshold
    }
    nx.draw_networkx_labels(H, pos, labels=labels, ax=ax, font_size=5.5,
                            font_weight="bold", font_color="#111111")

    # Colourbar
    sm = plt.cm.ScalarMappable(
        cmap="plasma",
        norm=mcolors.Normalize(vmin=0, vmax=int(reach_vals.max())),
    )
    sm.set_array([])
    fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.01,
                 label="Sum of colexification languages (cross-lingual reach)")

    n_nodes_full = len(G)
    n_edges_full = G.number_of_edges()
    n_nodes_gcc  = len(gcc)
    ax.set_title(
        f"Cross-lingual Colexification Graph  "
        f"(full: {n_nodes_full} nodes / {n_edges_full} edges  |  "
        f"largest component: {n_nodes_gcc} nodes  |  "
        f"shown: {len(H)} highest-degree nodes)\n"
        f"Nodes = Concepticon concepts  ·  "
        f"Edges = shared lemma in same language  ·  "
        f"Edge width ∝ number of languages  ·  "
        f"Colour = cross-lingual reach  ·  "
        f"Sources: {', '.join(sorted(LING_SOURCES))}  ·  max polysemy = {MAX_POLYSEMY}",
        fontsize=9, pad=8,
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


def plot_top_colexifications(
    G: nx.Graph,
    concepts: dict[str, dict],
    out_path: Path,
    top_n: int = 20,
) -> None:
    """Bar chart of the edges with the most cross-lingual colexifications."""
    edge_data = [
        (u, v, d["n_languages"], d["n_instances"],
         d["colexifications"][0]["lemma"] if d["colexifications"] else "?")
        for u, v, d in G.edges(data=True)
    ]
    edge_data.sort(key=lambda x: -x[2])
    top = edge_data[:top_n]

    labels = [
        f"{concepts[u]['gloss']} ↔ {concepts[v]['gloss']}\n(«{ex}»)"
        for u, v, _, _, ex in top
    ]
    n_langs = [x[2] for x in top]
    n_inst  = [x[3] for x in top]

    fig, ax = plt.subplots(figsize=(14, 8))
    y = np.arange(len(labels))
    bars = ax.barh(y, n_langs, color="steelblue", label="# languages")
    ax.barh(y, n_inst, left=n_langs, color="coral", alpha=0.6, label="# extra instances")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("Count")
    ax.set_title(f"Top {top_n} concept pairs by cross-lingual colexification strength")
    ax.legend()
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {out_path.name}")


# ---------------------------------------------------------------------------
# 5. Summary statistics
# ---------------------------------------------------------------------------

def print_stats(G: nx.Graph, concepts: dict[str, dict]) -> None:
    degrees = dict(G.degree())
    n_langs_per_edge = [d["n_languages"] for _, _, d in G.edges(data=True)]
    n_inst_per_edge  = [d["n_instances"]  for _, _, d in G.edges(data=True)]

    components = sorted(nx.connected_components(G), key=len, reverse=True)

    print(f"\n  Nodes          : {len(G)}")
    print(f"  Edges          : {G.number_of_edges()}")
    print(f"  Isolated nodes : {sum(1 for n in G.nodes if degrees[n] == 0)}")
    print(f"  Components     : {len(components)}  "
          f"(largest: {len(components[0])} nodes)")
    if n_langs_per_edge:
        print(f"  Edge n_languages: mean={np.mean(n_langs_per_edge):.2f}  "
              f"max={max(n_langs_per_edge)}")
        print(f"  Edge n_instances: mean={np.mean(n_inst_per_edge):.2f}  "
              f"max={max(n_inst_per_edge)}")

    print(f"\n  Top-15 concepts by colexification degree:")
    print(f"  {'Degree':>6}  {'ID':>6}  Gloss")
    for cid, deg in sorted(degrees.items(), key=lambda x: -x[1])[:15]:
        print(f"  {deg:>6}  {cid:>6}  {concepts[cid]['gloss']}")

    print(f"\n  Top-10 edges by n_languages:")
    top_edges = sorted(G.edges(data=True), key=lambda x: -x[2]["n_languages"])[:10]
    for u, v, d in top_edges:
        sample = [f"{c['language']}:«{c['lemma']}»" for c in d["colexifications"][:3]]
        print(f"  {concepts[u]['gloss']:<25} ↔ {concepts[v]['gloss']:<25} "
              f"({d['n_languages']} langs)  e.g. {', '.join(sample)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Loading BabelNet synsets from {CONCEPT_ZIP.name}...")
    concepts, index = load_babelnet(CONCEPT_ZIP, CONCEPT_TSV)
    print(f"  {len(concepts)} concepts")
    print(f"  {len(index)} (lang, lemma) pairs from linguistic sources (no underscores)")

    print(f"\nBuilding colexification graph (max_polysemy={MAX_POLYSEMY})...")
    G = build_colexification_graph(concepts, index, max_polysemy=MAX_POLYSEMY)
    print_stats(G, concepts)

    print(f"\nSaving outputs to {OUT_DIR} ...")

    print("  Exporting JSON...")
    export_json(G, concepts, OUT_DIR / "colexification_graph.json")

    print("  Plotting colexification graph...")
    plot_colexification_graph(G, concepts, OUT_DIR / "colexification_graph.png")

    print("  Plotting top colexification pairs...")
    plot_top_colexifications(G, concepts, OUT_DIR / "colexification_top_pairs.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
