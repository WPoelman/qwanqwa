"""
Generate language coverage LaTeX tables with qq.

Demonstrates you can produce language metadata tables for papers
in a few lines of code, instead of manually assembling data from multiple
sources.

Usage:
    uv run python case-studies/publication_tables/generate.py
"""

from __future__ import annotations

from pathlib import Path

from qq import Database

SCRIPT_DIR = Path(__file__).parent


def fmt_speakers(n: int | None) -> str:
    """Format speaker count for display in a table cell."""
    if n is None:
        return "---"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def tex_escape(s: str) -> str:
    """Escape special LaTeX characters."""
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        s = s.replace(char, replacement)
    return s


def primary_script_code(lang) -> str:
    """Return the canonical script code for a languoid, or '---' if unknown."""
    canonical = lang.canonical_scripts
    if canonical:
        return canonical[0].iso_15924
    codes = lang.script_codes
    if codes:
        return codes[0]
    return "---"


# Macrolanguages lack a root_family in qq; supply family names for display.
MACROLANGUAGE_FAMILIES = {
    "zho": "Sino-Tibetan",
    "ara": "Afro-Asiatic",
    "swa": "Atlantic-Congo",
    "msa": "Austronesian",
    "que": "Quechuan",
}

# BCP-47 codes for a realistic multilingual NLP benchmark (30 languages
# spanning families, scripts, and resource levels)
BENCHMARK_CODES = [
    "en",
    "fr",
    "de",
    "es",
    "pt",
    "it",
    "nl",
    "ru",
    "zh",
    "ja",
    "ko",
    "ar",
    "hi",
    "bn",
    "ta",
    "te",
    "th",
    "vi",
    "id",
    "ms",
    "sw",
    "yo",
    "ig",
    "ha",
    "am",
    "my",
    "km",
    "lo",
    "ka",
    "hy",
]


def generate_benchmark_table(access: Database) -> str:
    """Generate a LaTeX table of languages in a multilingual benchmark."""
    rows = []
    for code in BENCHMARK_CODES:
        try:
            lang = access.get(code)
        except KeyError:
            continue
        rows.append(
            {
                "name": lang.name,
                "endonym": lang.endonym or "---",
                "bcp47": lang.bcp_47 or "---",
                "iso3": lang.iso_639_3 or "---",
                "script": primary_script_code(lang),
                "speakers": fmt_speakers(lang.speaker_count),
                "family": (
                    lang.root_family.name if lang.root_family else MACROLANGUAGE_FAMILIES.get(lang.iso_639_3, "---")
                ),
            }
        )

    header = r"Language & Endonym & BCP-47 & ISO 639-3 & Script & Speakers & Family"
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{llcccrl}",
        r"\toprule",
        header + r" \\",
        r"\midrule",
    ]
    for row in rows:
        cells = [
            tex_escape(row["name"]),
            row["endonym"],  # endonyms contain Unicode, not LaTeX specials
            r"\texttt{" + row["bcp47"] + "}",
            r"\texttt{" + row["iso3"] + "}",
            row["script"],
            row["speakers"],
            tex_escape(row["family"]),
        ]
        lines.append(" & ".join(cells) + r" \\")
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Languages in the benchmark. Speaker counts from Ethnologue/CLDR via qq.}",
        r"\label{tab:benchmark-languages}",
        r"\end{table}",
    ]
    return "\n".join(lines)


def main() -> None:
    print("Loading qq database...")
    access = Database.load(names_path=None)
    print(f"Loaded {len(access.all_languoids)} languoids\n")

    out_dir = SCRIPT_DIR / "output"
    out_dir.mkdir(exist_ok=True)

    print("Generating: Benchmark language overview")
    tex = generate_benchmark_table(access)
    path = out_dir / "benchmark_languages.tex"
    path.write_text(tex + "\n")
    print(f"  -> {path.relative_to(SCRIPT_DIR)}")

    print(f"\nDone. Table written to {SCRIPT_DIR.name}/output/")
    print("\nTo use in LaTeX, add to your preamble:")
    print("  \\usepackage{booktabs}")
    print("Then \\input{output/benchmark_languages} in your document.")


if __name__ == "__main__":
    main()
