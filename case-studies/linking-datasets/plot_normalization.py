"""Visualize how QQ normalization changes cross-resource overlap.

Usage:
    uv run --with matplotlib,numpy python case-studies/linking-datasets/plot_normalization.py
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from link import (
    DATA_DIR,
    collect_codes,
    collect_codes_etymon,
    collect_codes_phonotacticon,
    resolve,
    resolve_phonotacticon,
)
from qq import Database
from qq.data_model import IdType

SCRIPT_DIR = Path(__file__).parent
PLOT_PATH = SCRIPT_DIR / "normalization_overlap.pdf"

QQ_ORANGE = "#c04f17"
QQ_GREEN = "#009b55"
QQ_BLUE = "#1f4b99"
QQ_MUTED = "#666666"
QQ_LINE = "#dddddd"
GRID_COLOR = QQ_LINE
RESOURCE_COLORS = [QQ_ORANGE, QQ_GREEN, QQ_MUTED]


def tint(color: str, white_mix: float = 0.72) -> tuple[float, float, float]:
    """Mix an interface color with white while preserving its hue."""
    rgb = mpl.colors.to_rgb(color)
    return tuple((1 - white_mix) * channel + white_mix for channel in rgb)


RAW_COLOR = tint(QQ_ORANGE, white_mix=0.18)
QQ_COLOR = tint(QQ_BLUE, white_mix=0.18)

PLOT_STYLE = {
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{newtxtext,newtxmath}",
    "font.family": "serif",
    "font.serif": ["Times New Roman"],
    "font.size": 8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def degree_counts(sets: list[set[str]]) -> Counter[int]:
    """Count items occurring in exactly one, two, three, or four sets."""
    universe = set().union(*sets)
    return Counter(sum(item in values for values in sets) for item in universe)


def load_identifier_sets() -> tuple[list[set[str]], list[set[str]]]:
    """Load raw resolved identifiers and their normalized QQ languoid sets."""
    db = Database.load(names_path=None)
    resolver = db.resolver

    concepticon_codes = collect_codes(
        DATA_DIR / "concepticon.zip",
        "concepticon_synsets/concepts_multilingual_senses.tsv",
        ["language"],
    )
    wordnet_codes = collect_codes(DATA_DIR / "wordnet.zip", "wn_synsets.csv", ["LANG"])
    etymon_codes = collect_codes_etymon(DATA_DIR / "etymon.zip", "etymon/etymwn.tsv")
    phono_glottocodes, phono_iso_codes = collect_codes_phonotacticon(
        DATA_DIR / "phonotacticon.zip",
        "Phonotacticon/Phonotacticon1_0.csv",
        resolver,
    )

    babelnet_lookup: list[tuple[IdType, Any]] = [
        (IdType.BCP_47, str.lower),
        (IdType.ISO_639_3, str.lower),
        (IdType.ISO_639_5, str.lower),
        (IdType.WIKIPEDIA, lambda code: code.lower().replace("_", "-")),
    ]
    etymon_lookup: list[tuple[IdType, Any]] = [
        (IdType.ISO_639_3, None),
        (IdType.ISO_639_5, None),
        (IdType.ISO_639_5, lambda code: code[2:] if code.startswith("p_") else code),
    ]

    concepticon, _ = resolve(resolver, concepticon_codes, babelnet_lookup)
    wordnet, _ = resolve(resolver, wordnet_codes, babelnet_lookup)
    etymon, _ = resolve(resolver, etymon_codes, etymon_lookup)
    phonotacticon, _, _ = resolve_phonotacticon(resolver, phono_glottocodes, phono_iso_codes)

    mappings = [concepticon, wordnet, etymon, phonotacticon]
    raw_sets = [set(mapping) for mapping in mappings]
    normalized_sets = [set(mapping.values()) for mapping in mappings]
    return raw_sets, normalized_sets


def add_example_table(ax) -> None:
    """Add compact examples of fragmented identifiers resolving together."""
    ax.set_axis_off()
    headers = ["Concept./WN", "Etymon", "Phonot.", "QQ"]
    x_positions = [0.16, 0.43, 0.69, 0.99]
    examples = [
        ("Dutch", ["NL", "nld", "dutc1256", "Dutch"]),
        ("German", ["DE", "deu", "stan1295", "German"]),
    ]

    ax.set_xlim(-0.15, 1.06)

    for x, header in zip(x_positions, headers):
        ax.text(x, 0.88, header, ha="center", va="center", fontweight="bold", fontsize=8)
    for row_index, (language, values) in enumerate(examples):
        y = 0.56 - row_index * 0.36
        ax.text(-0.12, y, language, ha="left", va="center", fontsize=8)
        for column, (x, value) in enumerate(zip(x_positions, values)):
            color = RESOURCE_COLORS[column] if column < 3 else QQ_BLUE
            ax.text(
                x,
                y,
                value,
                ha="center",
                va="center",
                fontsize=8,
                bbox={
                    "boxstyle": "round,pad=0.22",
                    "facecolor": tint(color),
                    "edgecolor": color,
                    "linewidth": 0.65,
                },
            )
        ax.annotate(
            "",
            xy=(0.89, y),
            xytext=(0.80, y),
            arrowprops={"arrowstyle": "->", "color": QQ_MUTED, "linewidth": 0.7},
        )


def main() -> None:
    print("Loading and resolving identifiers (this takes about a minute)...")
    raw_sets, normalized_sets = load_identifier_sets()
    raw_counts = degree_counts(raw_sets)
    normalized_counts = degree_counts(normalized_sets)

    degrees = np.arange(1, 5)
    raw_values = [raw_counts[degree] for degree in degrees]
    normalized_values = [normalized_counts[degree] for degree in degrees]

    print("Raw exact-identifier overlap:", dict(sorted(raw_counts.items())))
    print("Normalized languoid overlap:", dict(sorted(normalized_counts.items())))

    with mpl.rc_context(PLOT_STYLE):
        fig = plt.figure(figsize=(3.35, 2.9))
        grid = fig.add_gridspec(2, 1, height_ratios=[1.65, 0.85], hspace=0.65)
        ax = fig.add_subplot(grid[0])

        width = 0.34
        raw_bars = ax.bar(degrees - width / 2, raw_values, width, label="Raw code strings", color=RAW_COLOR)
        normalized_bars = ax.bar(
            degrees + width / 2,
            normalized_values,
            width,
            label="Resolved languoids",
            color=QQ_COLOR,
        )

        for bars in (raw_bars, normalized_bars):
            ax.bar_label(bars, padding=2, fontsize=7, fmt="%d")

        ax.set_xticks(degrees, ["1", "2", "3", "4"])
        ax.set_xlabel("Exact number of resources containing an item")
        ax.set_ylabel("Items")
        ax.set_ylim(0, max(raw_values + normalized_values) * 1.15)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", color=GRID_COLOR, linestyle="--", alpha=0.6, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.legend(
            frameon=True,
            facecolor="white",
            edgecolor=QQ_LINE,
            framealpha=1,
            fontsize=7.2,
            loc="upper right",
        )

        example_ax = fig.add_subplot(grid[1])
        add_example_table(example_ax)

        fig.savefig(PLOT_PATH, bbox_inches="tight")
        plt.close(fig)

    print(f"Plot saved to {PLOT_PATH}")


if __name__ == "__main__":
    main()
