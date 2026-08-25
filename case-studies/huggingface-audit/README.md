# HuggingFace Hub: Language Code Quality

How reliable are the language tags in datasets on the HuggingFace Hub? This case study scans datasets with HuggingFace `language:` metadata and cross-references every tag against qq to find deprecated, invalid, and misused codes.

## Running

```bash
# First run fetches metadata from the Hub API (~5 min), then caches it
uv run --with huggingface_hub,matplotlib,tqdm,pandas python case-studies/huggingface-audit/analyze.py

# Force re-fetch metadata (useful if the cache is stale)
uv run --with huggingface_hub,matplotlib,tqdm,pandas python case-studies/huggingface-audit/analyze.py --refresh
```

Requires `pandas`, `tqdm`, `matplotlib`, and `huggingface_hub` (installed ad-hoc via `--with`).

## What it does

1. **Fetches metadata** from the HuggingFace Hub API for datasets with language tags (only metadata, not dataset content).
2. **Classifies each language tag** by resolving it against qq's identifier database.
3. **Normalizes all Hub language tags** to QQ languoids and plots both dataset-level multilinguality and language-level dataset availability, including zero-coverage buckets.
4. **Reports results** across four categories:
   - **Valid** -- resolves to a known languoid
   - **Deprecated** -- the code is retired/split/merged (with reason and original standard)
   - **Country code** -- ISO 3166-1 alpha-2 code misused as a language tag (e.g., `cn`, `jp`, `us`)
   - **Unknown** -- not found in any standard

## Results

Scanning 119,583 datasets with language tags (8,237 unique language codes):

| Status | Count |
|---|---|
| Valid | 8,127 |
| Deprecated | 34 |
| Country code | 26 |
| Unknown | 50 |

**99.1% of unique codes resolve, including deprecated codes with replacements.** Across all Hub datasets with language tags, qq normalizes coverage for 7,943 languoids, while 19,369 QQ languoids have no HuggingFace dataset link. Most datasets are tagged as monolingual after normalization (104,586/119,583), and most covered languoids occur in fewer than 10 datasets. The remaining issues are:

- **34 deprecated codes** from retired ISO 639-3 entries (splits, merges, duplicates) and withdrawn BCP-47/ISO 639-1 codes (`iw` -> `he`, `in` -> `id`, `ji` -> `yi`, `mo` -> `ro`).
- **26 country codes** where dataset authors tagged a country instead of a language (e.g., `jp` instead of `ja`, `cn` instead of `zh`).
- **50 unknown codes** -- mostly HuggingFace-specific tags (`multilingual`, `code`), programming-language tags, private-use `q*` codes, and a few unresolvable entries.

## Output files

| File | Description |
|---|---|
| `hf_metadata.json` | Cached dataset metadata from the Hub API |
| `output/results.csv` | Per-code classification with status, detail, dataset count, and dataset list |
| `output/identifier_types.pdf` | Bar chart showing which identifier standards datasets use (valid codes only) |
| `output/dataset_language_coverage.csv` | Per-dataset count of normalized languoids after resolving language tags |
| `output/language_dataset_coverage.csv` | Per-languoid HuggingFace dataset availability, including QQ languoids with zero Hub coverage |
| `output/hf_dataset_coverage_buckets.pdf` | Bucket plot showing dataset multilinguality after normalization |
| `output/hf_languoid_coverage_buckets.pdf` | Bucket plot showing dataset availability per QQ languoid |
| `output/issues.tex` | LaTeX table summarising deprecated, country-code, and unknown issues by type |

## Frozen release input

`hf_metadata.json` is intentionally ignored by Git because of its size. The tracked `hf_metadata_2026-06-10.zip` contains only that frozen input, so it is included in GitHub and Zenodo source releases without being installed by the PyPI package. The tracked `snapshot_metadata.json` records checksums and sizes for both files, together with the collection date and evaluation environment. After extraction, the released scripts regenerate all ignored outputs from the frozen JSON input.
