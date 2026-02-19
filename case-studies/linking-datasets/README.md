# Linking Colexification Datasets via qq Language Identifiers

Four colex datasets, each using a different identifier standard. qq resolves them to a shared canonical ID.

## Datasets

| Dataset |  Identifier standard |
|---|---|
| Concepticon BabelNet synsets | BabelNet codes: primarily uppercase ISO 639-1 (`IT`, `ZH`), but also uppercase ISO 639-3 for historical languages (`AKK`, `ANG`) and Wikipedia language codes (`ZH_YUE`, `BAT_SMG`) |
| WordNet synsets | Same BabelNet convention as Concepticon |
| Etymon (Etymological Wordnet) | ISO 639-3 lowercase (`eng`, `nld`), ISO 639-5 family codes (`nah`), and Etymon's own proto-language notation (`p_ine`, `p_gem`) |
| Phonotacticon | Glottocodes (`dutc1256`) with ISO 639-3 as fallback |

## Running

```bash
uv run python case-studies/linking-datasets/link.py
```

Reading the two large files takes about a minute. Only the language column is parsed; no lexical data is loaded into memory.

## Results

| Dataset | Unique codes | Resolved by qq | Resolution rate |
|---|---|---|---|
| Concepticon (BabelNet) | 600 | 592 | 98.7% |
| WordNet synsets | 520 | 514 | 98.8% |
| Etymon | 397 | 397 | 100% |
| Phonotacticon | 519 | 517 | 99.6% |

**102 languages appear in all four datasets**

Unresolved codes are listed in `unresolved.txt`.

### Cross-dataset coverage

| Overlap | Languages |
|---|---|
| Concepticon only | 55 |
| WordNet only | 0 |
| Etymon only | 91 |
| Phonotacticon only | 325 |
| Concepticon ∩ WordNet | 509 |
| Concepticon ∩ Etymon | 298 |
| Concepticon ∩ Phonotacticon | 185 |
| WordNet ∩ Etymon | 282 |
| WordNet ∩ Phonotacticon | 178 |
| Etymon ∩ Phonotacticon | 109 |
| All three (excl. Phonotacticon) | 282 |
| All four datasets | 102 |

WordNet only = 0 because WordNet uses the same BabelNet identifier format as Concepticon, and every language in WordNet also appears in Concepticon. The 509-language WordNet ∩ Concepticon intersection covers the entire WordNet.

### Linking examples

The same language expressed in each dataset's identifier system, resolved to one languoid:

```
  Language               Canonical ID   Concepticon    WordNet        Etymon       Phonotacticon
  ──────────────────────────────────────────────────────────────────────────────────────────────
  Dutch                  lang:006448    NL             NL             nld          dutc1256
  German                 lang:006636    DE             DE             deu          stan1295
  Turkish                lang:000917    TR             TR             tur          nucl1301
  Russian                lang:006745    RU             RU             rus          russ1263
  Japanese               lang:005185    JA             JA             jpn          nucl1643
  Swahili                lang:001597    SW             SW             swa          -
```
