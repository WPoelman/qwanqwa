"""
Scan HuggingFace Hub datasets for deprecated language codes.

Fetches dataset metadata from the HuggingFace Hub API (language tags only,
not dataset content), filters to multilingual datasets (>=10 languages),
and cross-references every language tag against qq to classify it as
valid, deprecated, or unknown.

Usage:
    uv run --with huggingface_hub,matplotlib,tqdm python case-studies/huggingface-audit/analyze.py
    uv run --with huggingface_hub,matplotlib,tqdm python case-studies/huggingface-audit/analyze.py --refresh
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
from huggingface_hub import HfApi
from tqdm import tqdm

from qq import Database, IdType
from qq.constants import LOG_SEP

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
CACHE_PATH = SCRIPT_DIR / "hf_metadata.json"
DEFAULT_MIN_LANGUAGES = 10

# ID types to try when classifying a code, in priority order.
LOOKUP_ORDER = [
    IdType.BCP_47,
    IdType.ISO_639_1,
    IdType.ISO_639_3,
    IdType.ISO_639_2T,
    IdType.ISO_639_2B,
    IdType.ISO_639_5,
    IdType.GLOTTOCODE,
    IdType.WIKIDATA_ID,
    IdType.WIKIPEDIA,
]


def fetch_hf_metadata(refresh: bool = False) -> list[dict]:
    """Fetch dataset metadata from HuggingFace Hub, with caching.

    Returns a list of dicts with 'id' and 'languages' keys for all datasets
    that have at least one language tag. Filtering by minimum language count
    is done after loading.
    """
    if CACHE_PATH.exists() and not refresh:
        print(f"Loading cached metadata from {CACHE_PATH.name}")
        return json.loads(CACHE_PATH.read_text())

    print("Fetching dataset metadata from HuggingFace Hub...")
    api = HfApi()

    results = []
    total = 0
    for ds in tqdm(api.list_datasets(), desc="Scanning datasets", unit=" datasets"):
        total += 1
        if not ds.tags:
            continue
        langs = [t.removeprefix("language:") for t in ds.tags if t.startswith("language:")]
        if langs:
            results.append({"id": ds.id, "languages": langs})

    print(f"Found {len(results)} datasets with language tags (out of {total} total)")

    CACHE_PATH.write_text(json.dumps(results, indent=2))
    print(f"Cached metadata to {CACHE_PATH.name}")
    return results


def classify_code(resolver, store, code: str) -> tuple[str, str | None]:
    """Classify a language code as valid, deprecated, country_code, or unknown.

    Returns (status, detail) where status is 'valid' | 'deprecated' | 'country_code' | 'unknown'.
    """
    # First pass: try to resolve the code
    for id_type in LOOKUP_ORDER:
        canonical = resolver.resolve(id_type, code)
        if canonical is not None:
            if resolver.is_deprecated(id_type, code):
                reason = resolver.get_deprecation(id_type, code) or ""
                return "deprecated", reason
            return "valid", None

    # Second pass: check if deprecated without a replacement
    for id_type in LOOKUP_ORDER:
        if resolver.is_deprecated(id_type, code):
            reason = resolver.get_deprecation(id_type, code) or ""
            return "deprecated", reason

    # Check if it's a known geographic region/country code misused as a language tag
    if store.get(f"region:{code.lower()}") is not None:
        return "country_code", "ISO 3166-1 country code, not a language code"

    return "unknown", None


_ID_TYPE_LABEL: dict[IdType, str] = {
    IdType.BCP_47: "BCP-47",
    IdType.ISO_639_1: "ISO 639-1",
    IdType.ISO_639_3: "ISO 639-3",
    IdType.ISO_639_2T: "ISO 639-2/T",
    IdType.ISO_639_2B: "ISO 639-2/B",
    IdType.ISO_639_5: "ISO 639-5",
    IdType.GLOTTOCODE: "Glottocode",
    IdType.WIKIDATA_ID: "Wikidata",
    IdType.WIKIPEDIA: "Wikipedia",
}


def identify_code_type(resolver, store, code: str) -> str:
    """Determine which identifier standard a code belongs to.

    Checks the most specific type first so that e.g. "en" is reported as
    ISO 639-1 rather than the more generic BCP-47.
    """
    # Check most-specific types first so "en" is reported as ISO 639-1, not BCP-47.
    # Check is_deprecated alongside resolve: a deprecated-with-replacement code still
    # resolves, so we must check deprecation status here rather than as a fallback.
    for id_type in [
        IdType.ISO_639_1,
        IdType.ISO_639_3,
        IdType.ISO_639_2T,
        IdType.ISO_639_2B,
        IdType.ISO_639_5,
        IdType.GLOTTOCODE,
        IdType.WIKIDATA_ID,
        IdType.WIKIPEDIA,
        IdType.BCP_47,
    ]:
        if resolver.resolve(id_type, code):
            label = _ID_TYPE_LABEL[id_type]
            return label + " (deprecated)" if resolver.is_deprecated(id_type, code) else label
    for id_type in LOOKUP_ORDER:
        if resolver.is_deprecated(id_type, code):
            return _ID_TYPE_LABEL[id_type] + " (deprecated)"
    if store.get(f"region:{code.lower()}") is not None:
        return "Country code"
    return "Unknown"


def write_issues_table(
    dep_by_type: dict[str, list[str]],
    cc_codes: list[str],
    unk_codes: list[str],
    code_datasets: dict[str, list[str]],
    out_path: Path,
) -> None:
    """Write a LaTeX overview table of all problematic codes on the HF Hub."""

    def ds_uses(codes: list[str]) -> int:
        return sum(len(code_datasets[c]) for c in codes)

    dep_rows = sorted(
        ((label.removesuffix(" (deprecated)"), len(codes), ds_uses(codes)) for label, codes in dep_by_type.items()),
        key=lambda r: r[2],
        reverse=True,
    )

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"Category & Codes & Dataset uses \\",
        r"\midrule",
    ]
    for label, n_codes, n_uses in dep_rows:
        lines.append(f"{label} (deprecated) & {n_codes} & {n_uses:,} \\\\")
    lines.append(r"\midrule")
    lines.append(f"Country code & {len(cc_codes)} & {ds_uses(cc_codes):,} \\\\")
    lines.append(f"Unknown & {len(unk_codes)} & {ds_uses(unk_codes):,} \\\\")
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Problematic language codes found on the HuggingFace Hub.}",
        r"\label{tab:hf-issues}",
        r"\end{table}",
    ]
    out_path.write_text("\n".join(lines) + "\n")
    print(f"  -> {out_path.relative_to(out_path.parent.parent)}")


def plot_identifier_distribution(
    code_types: dict[str, str],
    code_datasets: dict[str, list[str]],
    plot_path: Path,
) -> None:
    """Plot how many datasets use each identifier type."""
    import matplotlib as mpl
    import matplotlib.pyplot as plt

    type_datasets: dict[str, set[str]] = defaultdict(set)
    for code, type_name in code_types.items():
        if "(deprecated)" not in type_name:
            for ds_id in code_datasets[code]:
                type_datasets[type_name].add(ds_id)

    sorted_items = sorted(type_datasets.items(), key=lambda x: len(x[1]))
    labels = [item[0] for item in sorted_items]
    counts = [len(item[1]) for item in sorted_items]

    palette = [
        "#c4dfe6",
        "#a8d5ba",
        "#d4c4a8",
        "#c4b8d4",
        "#e0b4b4",
        "#b8c9d4",
        "#d4d4a8",
        "#d4a8c4",
        "#a8c4d4",
        "#c4d4a8",
    ]
    colors = [palette[i % len(palette)] for i in range(len(labels))]

    with mpl.rc_context({"font.family": "serif"}):
        size = max(3, len(labels) * 0.45)
        fig, ax = plt.subplots(figsize=(size, size))
        bars = ax.barh(labels, counts, color=colors, edgecolor="white", linewidth=0.8)

        max_count = max(counts) if counts else 1
        for bar, count in zip(bars, counts):
            ax.text(
                bar.get_width() + max_count * 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"{count:,}",
                va="center",
                fontsize=12,
            )

        ax.set_xlabel("Number of datasets", fontsize=14)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="y", labelsize=13)
        ax.tick_params(axis="x", labelsize=12)
        ax.set_xlim(0, max_count * 1.12)
        ax.grid(axis="x", linestyle="--", alpha=0.25)
        ax.set_axisbelow(True)

        plt.tight_layout()
        plt.savefig(plot_path, bbox_inches="tight")
        print(f"\nPlot saved to {plot_path.name}")
        plt.close()


def analyze(datasets: list[dict], ld: Database, csv_path: Path, plot_path: Path, out_dir: Path) -> None:
    """Analyze datasets and print report."""
    resolver = ld.resolver
    store = ld.store

    # Classify every code and track which datasets use it
    code_status: dict[str, tuple[str, str | None]] = {}
    code_datasets: dict[str, list[str]] = defaultdict(list)
    dataset_stats: dict[str, dict[str, list[str]]] = {}

    for ds in datasets:
        ds_id = ds["id"]
        ds_breakdown: dict[str, list[str]] = defaultdict(list)

        for code in ds["languages"]:
            code_datasets[code].append(ds_id)
            if code not in code_status:
                code_status[code] = classify_code(resolver, store, code)
            status, _ = code_status[code]
            ds_breakdown[status].append(code)

        dataset_stats[ds_id] = dict(ds_breakdown)

    # Build results DataFrame
    rows = []
    for code, (status, detail) in code_status.items():
        ds_list = code_datasets[code]
        rows.append(
            {
                "code": code,
                "status": status,
                "detail": detail or "",
                "dataset_count": len(ds_list),
                "datasets": ";".join(ds_list),
            }
        )

    df = pd.DataFrame(rows).sort_values(["status", "dataset_count"], ascending=[True, False]).reset_index(drop=True)
    df.to_csv(csv_path, index=False)
    print(f"\nResults written to {csv_path.name} ({len(df)} codes)")

    # --- Plot ---
    code_types = {code: identify_code_type(resolver, store, code) for code in code_status}
    plot_identifier_distribution(code_types, code_datasets, plot_path)

    # --- Summary ---
    counts = df["status"].value_counts()
    print(LOG_SEP)
    print("HUGGINGFACE HUB: DEPRECATED LANGUAGE CODE ANALYSIS")
    print(LOG_SEP)
    print(f"\nDatasets scanned:   {len(datasets)}")
    print(f"Unique codes found: {len(df)}")
    for status in ["valid", "deprecated", "country_code", "unknown"]:
        print(f"  {status.capitalize():<16}  {counts.get(status, 0)}")

    # --- Deprecated codes ---
    dep = df[df["status"] == "deprecated"].copy()
    dep_by_type: dict[str, list[str]] = defaultdict(list)
    if not dep.empty:
        print(LOG_SEP)
        print("DEPRECATED CODES")
        print(LOG_SEP)
        dep_display = dep[["code", "dataset_count", "detail"]].rename(
            columns={"dataset_count": "datasets", "detail": "reason"}
        )
        print(dep_display.to_string(index=False))

        print(LOG_SEP)
        print("DEPRECATED CODES BY IDENTIFIER TYPE")
        print(LOG_SEP)
        for code in dep["code"]:
            dep_by_type[code_types[code]].append(code)
        for type_label, type_codes in sorted(dep_by_type.items()):
            ds_count = sum(len(code_datasets[c]) for c in type_codes)
            print(f"  {type_label:<22} {len(type_codes):3d} codes, {ds_count:5d} dataset uses")

    # --- Country codes ---
    cc = df[df["status"] == "country_code"].copy()
    if not cc.empty:
        print(LOG_SEP)
        print("COUNTRY CODES (ISO 3166-1 codes misused as language tags)")
        print(LOG_SEP)
        cc_display = cc[["code", "dataset_count"]].rename(columns={"dataset_count": "datasets"})
        print(cc_display.to_string(index=False))

    # --- Unknown codes ---
    unk = df[df["status"] == "unknown"].copy()
    if not unk.empty:
        print(LOG_SEP)
        print("UNKNOWN CODES (not found in qq)")
        print(LOG_SEP)
        unk_display = unk[["code", "dataset_count"]].rename(columns={"dataset_count": "datasets"})
        print(unk_display.to_string(index=False))

    # --- Issues table (LaTeX) ---
    write_issues_table(
        dep_by_type,
        list(cc["code"]),
        list(unk["code"]),
        code_datasets,
        out_dir / "issues.tex",
    )

    # --- Top offenders ---
    offender_rows = []
    for ds_id, stats in dataset_stats.items():
        dep_codes = stats.get("deprecated", [])
        unk_codes = stats.get("unknown", [])
        cc_codes = stats.get("country_code", [])
        if dep_codes or unk_codes or cc_codes:
            offender_rows.append(
                {
                    "dataset": ds_id,
                    "deprecated": len(dep_codes),
                    "unknown": len(unk_codes),
                    "country_code": len(cc_codes),
                    "total_tags": sum(len(v) for v in stats.values()),
                    "deprecated_codes": ", ".join(sorted(dep_codes)),
                    "unknown_codes": ", ".join(sorted(unk_codes)),
                    "country_codes": ", ".join(sorted(cc_codes)),
                }
            )

    if offender_rows:
        offenders = (
            pd.DataFrame(offender_rows)
            .sort_values(["deprecated", "unknown", "country_code"], ascending=False)
            .head(15)
            .reset_index(drop=True)
        )

        print(LOG_SEP)
        print("TOP OFFENDERS (datasets with most deprecated/unknown/country codes)")
        print(LOG_SEP)
        print(offenders[["dataset", "total_tags", "deprecated", "unknown", "country_code"]].to_string(index=False))

        # Show detail for top 5
        for _, row in offenders.head(5).iterrows():
            print(f"\n  {row['dataset']}  ({row['total_tags']} language tags)")
            if row["deprecated_codes"]:
                print(f"    Deprecated   ({row['deprecated']}): {row['deprecated_codes']}")
            if row["unknown_codes"]:
                print(f"    Unknown      ({row['unknown']}): {row['unknown_codes']}")
            if row["country_codes"]:
                print(f"    Country code ({row['country_code']}): {row['country_codes']}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan HuggingFace Hub datasets for deprecated language codes.")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch metadata from HuggingFace Hub")
    parser.add_argument(
        "--min-languages",
        type=int,
        default=DEFAULT_MIN_LANGUAGES,
        help="Minimum language tags per dataset (default: 10)",
    )
    args = parser.parse_args()

    min_lang = args.min_languages
    suffix = f"_min{min_lang}" if min_lang != DEFAULT_MIN_LANGUAGES else ""
    csv_path = OUTPUT_DIR / f"results{suffix}.csv"
    plot_path = OUTPUT_DIR / f"identifier_types{suffix}.pdf"

    # fetch/load HF metadata
    all_datasets = fetch_hf_metadata(refresh=args.refresh)
    datasets = [ds for ds in all_datasets if len(ds["languages"]) >= min_lang]
    print(f"Filtered to {len(datasets)} datasets with >={min_lang} language tags")

    if not datasets:
        print("No datasets found. Try --refresh if using a stale cache.")
        exit(0)

    # analyze against qq
    print("Loading qq database...")
    ld = Database.load(names_path=None)
    print(f"Loaded {len(ld.all_languoids)} languoids")

    out_dir = OUTPUT_DIR
    out_dir.mkdir(exist_ok=True, parents=True)

    analyze(datasets, ld, csv_path, plot_path, out_dir)


if __name__ == "__main__":
    main()
