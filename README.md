# Qwanqwa (`qq`): Language Metadata

A unified language metadata toolkit for NLP: identifiers, scripts, speakers, geographic data, and traversable relationships across ~27,256 languoids.

**Name**: **Q**wan**q**wa is a phonetic spelling of 'ቋንቋ', which means *language* in Amharic; `qq` is short to type.

> Demo video: https://youtu.be/D9MmGCmJeNg

## Features

- **Identifiers**: BCP-47, ISO 639-1, ISO 639-3, ISO 639-2B, ISO 639-2T, ISO 639-5, Glottocode, Wikidata ID, Wikipedia ID, NLLB-style codes
- **Geographic information**: Countries, subdivisions, regions, which can be traversed, including from languoids and back
- **Speaker information**: Population counts, UNESCO endangerment status
- **Writing systems**: ISO 15924 script codes with canonical/historical metadata
- **Multilingual names**: Language names in 500+ languages
- **Relationships**: Traversable graph of language families, scripts, and geographic regions
- **Phylogenetic data**: Language family trees from Glottolog

## Languoids

In `qq`, language-like entities are referred to as [*Languoids*](http://www.glottopedia.de/index.php/Languoid): this includes dialects, macro-languages, and language families, not just individual languages. Not all languoids have coverage for all features.

## Installation

```bash
uv add qwanqwa
# or
pip install qwanqwa
```

## Quick Start

```python
from qq import Database, IdType

# Load the pre-compiled database
db = Database.load()

# Get a language by BCP-47 code (default)
dutch = db.get("nl")
print(dutch.name)          # "Dutch"
print(dutch.iso_639_3)     # "nld"
print(dutch.speaker_count) # 24085200

# Also works with ISO 639-3, Glottocode, etc.
dutch2 = db.get("nld", id_type=IdType.ISO_639_3)
dutch3 = db.get("dutc1256", id_type=IdType.GLOTTOCODE)
dutch4 = db.guess("dut") # guessing works too
# This will all resolve to the same languoid
assert dutch.id == dutch2.id == dutch3.id == dutch4.id

# Search by name
results = db.search("Chinese")
for lang in results:
    print(f"{lang.name} ({lang.glottocode})")
```

**Important**: `qq` makes a strict distinction between `None` (*don't know*) and `False` (*it is not the case*). When checking boolean attributes, prefer explicit checks over truthiness: use `if script.is_canonical is None:` rather than `if not script.is_canonical:`.

## Traversal

Languoids, scripts, and geographic regions are all part of the same graph, which can be traversed:

```python
dutch = db.get("nl")

# Language family navigation (Glottolog tree)
dutch.parent             # Global Dutch
dutch.parent.parent      # Modern Dutch
dutch.family_tree        # [Global Dutch, Modern Dutch, ..., West Germanic, Germanic, Indo-European]
dutch.siblings           # [Afrikaansic, Javindo, Petjo]
dutch.children           # [North Hollandish, Central Northern Dutch, ...]
dutch.descendants()      # All descendants (recursive)

# Writing systems
dutch.scripts            # [Script(Latin, code=Latn)]
dutch.script_codes       # ["Latn"]
dutch.canonical_scripts  # scripts marked canonical in LinguaMeta

# Geographic regions
dutch.regions            # [Aruba, Belgium, ..., Netherlands, Suriname, ...]
dutch.country_codes      # ["AW", "BE", "BQ", "CW", "NL", "SR", "SX"]

# Reverse traversal to script
latin = dutch.scripts[0]
latin.languoids          # All languages using Latin script

# Cross-domain queries
dutch.languoids_with_same_script   # other languages sharing any script
dutch.languoids_in_same_region     # other languages in the same regions
```

## Identifiers and Conversion

```python
from qq import IdType

# Automatic detection
lang = db.guess("nld")   # tries all identifier types

# Explicit conversion
db.convert("nl", IdType.BCP_47, IdType.ISO_639_3)    # "nld"
db.convert("nld", IdType.ISO_639_3, IdType.GLOTTOCODE) # "dutc1256"

# Conversion where you don't know or care what the source is, just the target.
# Useful for normalizing multiple standards to one
db.convert("nl", IdType.ISO_639_3)    # "nld"
db.convert("dutc1256", IdType.ISO_639_3) # "nld"

# NLLB-style codes
dutch.nllb_codes()              # ["nld_Latn"]
dutch.nllb_codes(use_bcp_47=True) # ["nl_Latn"]
```

## Multilingual Names

```python
# Name of Dutch in French
dutch.name_in("fr")    # "néerlandais"
dutch.name_in(french)  # also accepts a Languoid object

# Native name
dutch.endonym  # "Nederlands"
```

## Command Line Interface

```bash
# Look up a language
qq get nl
qq get nld --type ISO_639_3

# Search by name
qq search Dutch

# Database statistics and validation
qq validate

# Rebuild the database from sources
qq rebuild

# Check source status
qq status

# Update sources (only needed if you want to rebuild the database,
# not necessary in normal use)
qq update
```

## Examples

See the [`examples/`](https://github.com/WPoelman/qwanqwa/tree/main/examples/) directory for runnable scripts covering:
- `01_basic_usage.py`: Loading and accessing attributes
- `02_identifiers.py`: Working with identifier types and retired codes
- `03_conversion.py`: Converting between identifiers
- `04_traversal.py`: Language family navigation
- `05_search.py`: Searching and filtering
- `06_names.py`: Multilingual name data
- `07_geographic.py`: Geographic regions and countries
- `08_relations.py`: Relationship graph traversal
- `09_advanced_queries.py`: Complex queries and statistics
- `10_linking_datasets.py`: Joining datasets that use different identifier systems
- `11_normalizing_datasets.py`: Normalizing mixed identifier codes to a single standard

## Case studies

The [`case-studies/`](https://github.com/WPoelman/qwanqwa/tree/main/case-studies/) directory contains runnable analyses that use qq:

- **[`huggingface-audit/`](https://github.com/WPoelman/qwanqwa/tree/main/case-studies/huggingface-audit/)**: Scans all multilingual datasets on the HuggingFace Hub and classifies every `language:` tag as valid, deprecated, a misused country code, or unknown. qq resolves 99.2% of the 8,189 codes; the rest are deprecated, misused country codes, or HuggingFace-specific tags.
- **[`linking-datasets/`](https://github.com/WPoelman/qwanqwa/tree/main/case-studies/linking-datasets/)**: Links four lexical datasets (Concepticon, WordNet, Etymon, Phonotacticon) that each use a different identifier standard. qq resolves these four to a shared canonical ID: 102 languages are covered by all four.
- **[`latex-tables/`](https://github.com/WPoelman/qwanqwa/tree/main/case-studies/latex-tables/)**: Generates a LaTeX table of language metadata (identifiers, scripts, speaker counts, families) for an imaginary 30-language NLP benchmark.
- **[`identifier-coverage/`](https://github.com/WPoelman/qwanqwa/tree/main/case-studies/identifier-coverage/)**: Visualizes which combinations of identifier standards (Glottocode, ISO 639-3, ISO 639-1, Wikidata) cover which languoids as an UpSet plot.

## Sources

This project builds on the work of many people. See [`docs/sources.md`](https://github.com/WPoelman/qwanqwa/blob/main/docs/sources.md) for the full list. All sources are available under Creative Commons BY or BY-SA licenses.

## Development

To rebuild the database from sources, install with the `build` extras:

```bash
uv add qwanqwa[build]
# or
pip install qwanqwa[build]
```

To install for local development:

```bash
git clone https://github.com/WPoelman/qwanqwa
cd qwanqwa
uv sync --group dev
```

## License

The data sources qq incorporates have different licenses, see [here](https://github.com/WPoelman/qwanqwa/blob/main/docs/sources.md).

We follow [this](https://epiverse-trace.github.io/posts/data-licensing-cran.html#licensing-code-and-data-in-one-r-package) example and license the software as [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) and the data as [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

This means for instance that any data issues we encounter will be openly reported to the upstream sources (in accordance with ShareAlike principles of CC BY-SA), but that the software will ship with a compiled dataset (in accordance with the redistribution CC BY and CC BY-SA allow).

Ideally we'd use CC BY-SA for everything, but this is highly [discouraged](https://creativecommons.org/faq/#can-i-apply-a-creative-commons-license-to-software) for software, even by Creative Commons themselves.
