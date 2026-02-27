"""
Visualize identifier coverage across all qq languoids as an UpSet plot.

Shows which combinations of identifier standards (Glottocode, ISO 639-3,
ISO 639-1, BCP-47, Wikidata) cover which languoids, and how many fall into
each intersection.

Usage:
    uv run --with upsetplot,matplotlib python case-studies/identifier-coverage/plot.py
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
    "iso_639_1": "ISO-639-1",
    "iso_639_2b": "ISO-639-2B",
    "iso_639_3": "ISO-639-3",
    "iso_639_5": "ISO-639-5",
    "wikipedia": "Wikipedia",
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

    with mpl.rc_context({"font.family": "serif", "font.size": 7}):
        upset = UpSet(
            membership,
            sort_by="cardinality",
            show_counts=True,
            show_percentages=True,
            min_subset_size=10,
            facecolor="#8eaec0",
            element_size=36,
            intersection_plot_elements=3,
        )
        fig = upset.plot()
        fig["intersections"].set_ylabel("Languoids", fontsize=10)
        fig["intersections"].grid(axis="y", color="lightgrey", linestyle="--", alpha=0.5)
        fig["intersections"].set_axisbelow(True)
        _, current_ymax = fig["intersections"].get_ylim()
        fig["intersections"].set_ylim(0, current_ymax * 0.95)  # top get rid of overlapping labels

        fig["totals"].set_xlabel("Total", fontsize=10)
        fig["totals"].grid(axis="x", color="lightgrey", linestyle="--", alpha=0.5)
        fig["totals"].set_axisbelow(True)

        plt.savefig(PLOT_PATH, bbox_inches="tight")
        print(f"\nPlot saved to {PLOT_PATH}")
        plt.close()


if __name__ == "__main__":
    main()
