# HuggingFace Hub: Language Code Quality

How reliable are the language tags in datasets on the HuggingFace Hub? This case study scans multilingual datasets and cross-references every `language:` tag against qq to find deprecated, invalid, and misused codes.

## Running

```bash
# First run fetches metadata from the Hub API (~5 min), then caches it
uv run --with huggingface_hub,matplotlib,tqdm,pandas python case-studies/huggingface-audit/analyze.py

# Force re-fetch metadata (useful if the cache is stale)
uv run --with huggingface_hub,matplotlib,tqdm,pandas python case-studies/huggingface-audit/analyze.py --refresh
```

Requires `pandas`, `tqdm`, `matplotlib`, and `huggingface_hub` (installed ad-hoc via `--with`).

## What it does

1. **Fetches metadata** from the HuggingFace Hub API for all datasets with >10 language tags (only metadata, not dataset content).
2. **Classifies each language tag** by resolving it against qq's identifier database.
3. **Reports results** across four categories:
   - **Valid** -- resolves to a known languoid
   - **Deprecated** -- the code is retired/split/merged (with reason and original standard)
   - **Country code** -- ISO 3166-1 alpha-2 code misused as a language tag (e.g., `cn`, `jp`, `us`)
   - **Unknown** -- not found in any standard

## Results

Scanning 1,286 multilingual datasets (8,189 unique language codes):

| Status | Count |
|---|---|
| Valid | 8,122 |
| Deprecated | 23 |
| Country code | 19 |
| Unknown | 25 |

**99.2% of codes resolve correctly.** The remaining issues:

- **23 deprecated codes** from retired ISO 639-3 entries (splits, merges, duplicates) and withdrawn BCP-47/ISO 639-1 codes (`iw` -> `he`, `in` -> `id`, `ji` -> `yi`, `mo` -> `ro`).
- **19 country codes** where dataset authors tagged a country instead of a language (e.g., `jp` instead of `ja`, `cn` instead of `zh`).
- **25 unknown codes** -- mostly HuggingFace-specific tags (`multilingual`, `code`, `xx`), private-use `q*` codes, and a few unresolvable entries.

## Output files

| File | Description |
|---|---|
| `hf_metadata.json` | Cached dataset metadata from the Hub API |
| `output/results.csv` | Per-code classification with status, detail, dataset count, and dataset list |
| `output/identifier_types.pdf` | Bar chart showing which identifier standards datasets use (valid codes only) |
| `output/issues.tex` | LaTeX table summarising deprecated, country-code, and unknown issues by type |
