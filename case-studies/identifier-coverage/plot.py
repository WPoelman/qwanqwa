"""
Visualize identifier coverage across all qq languoids as an UpSet plot.

Shows which combinations of identifier standards (Glottocode, ISO 639-3,
ISO 639-1, BCP-47, Wikidata) cover which languoids, and how many fall into
each intersection.

Usage:
    uv run --with upsetplot,matplotlib python case-studies/identifier_coverage/plot.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from upsetplot import UpSet

from qq import Database

# upsetplot 0.9 triggers FutureWarnings from its own pandas usage
warnings.filterwarnings("ignore", category=FutureWarning, module="upsetplot")


SCRIPT_DIR = Path(__file__).parent
PLOT_PATH = SCRIPT_DIR / "identifier_coverage.pdf"

ATTR_LABELS = {
    "glottocode": "Glottocode",
    "iso_639_3": "ISO 639-3",
    "iso_639_1": "ISO 639-1",
    "wikidata_id": "Wikidata",
}


def main() -> None:
    print("Loading qq database...")
    ld = Database.load(names_path=None)
    languoids = ld.all_languoids
    print(f"Loaded {len(languoids)} languoids")

    rows = []
    for lang in languoids:
        row = {label: getattr(lang, attr, None) is not None for attr, label in ATTR_LABELS.items()}
        rows.append(row)

    df = pd.DataFrame(rows)

    print("\nIdentifier coverage:")
    for col in df.columns:
        n = df[col].sum()
        print(f"  {col:<14} {n:>6} / {len(df)} ({100 * n / len(df):.1f}%)")

    membership = df.groupby(list(df.columns)).size()

    with mpl.rc_context({"font.family": "serif", "font.size": 8}):
        upset = UpSet(
            membership,
            sort_by="cardinality",
            show_counts=True,
            show_percentages=True,
            min_subset_size=10,
            facecolor="#8eaec0",
            element_size=46,
            intersection_plot_elements=8,
        )
        fig = upset.plot()
        fig["intersections"].set_ylabel("Languoids", fontsize=10)
        fig["totals"].set_xlabel("Total", fontsize=10)

        plt.savefig(PLOT_PATH, bbox_inches="tight")
        print(f"\nPlot saved to {PLOT_PATH}")
        plt.close()


if __name__ == "__main__":
    main()
