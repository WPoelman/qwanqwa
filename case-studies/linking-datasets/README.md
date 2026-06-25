# Linking Colexification Datasets via qq Language Identifiers

Five colex datasets, each using a different identifier standard. qq resolves them to a shared canonical ID.

## Datasets

| Dataset |  Identifier standard |
|---|---|
| Concepticon BabelNet synsets | BabelNet codes: primarily uppercase ISO 639-1 (`IT`, `ZH`), but also uppercase ISO 639-3 for historical languages (`AKK`, `ANG`) and Wikipedia language codes (`ZH_YUE`, `BAT_SMG`) |
| WordNet synsets | Same BabelNet convention as Concepticon |
| Etymon (Etymological Wordnet) | ISO 639-3 lowercase (`eng`, `nld`), ISO 639-5 family codes (`nah`), and Etymon's own proto-language notation (`p_ine`, `p_gem`) |
| Phonotacticon | Glottocodes (`dutc1256`) with ISO 639-3 as fallback |
| NoRaRe | ISO 639-1 lowercase (`en`, `de`) and some ISO 639-3 codes from the `LANGUAGE` column |

## Running

```bash
uv run python case-studies/linking-datasets/link.py
```

Reading the two large files takes about a minute. Only the language column is parsed; no lexical data is loaded into memory.

The NoRaRe input is read from `data/norare-data.zip`. If it is missing, the scripts download the current GitHub archive from `concepticon/norare-data` into the ignored data directory. Both the older `norare-data/norare.tsv` zip layout and the normal GitHub `norare-data-master/norare.tsv` archive layout are supported.

## Results

| Dataset | Unique codes | Resolved by qq | Resolution rate |
|---|---|---|---|
| Concepticon (BabelNet) | 600 | 592 | 98.7% |
| WordNet synsets | 520 | 514 | 98.8% |
| Etymon | 397 | 396 | 99.7% |
| Phonotacticon | 519 | 517 | 99.6% |
| NoRaRe | 53 | 53 | 100% |

**102 languages appear in the original four datasets; 34 languages appear in all five datasets including NoRaRe.**

Unresolved codes are listed in `unresolved.txt`.

### Cross-dataset coverage

| Overlap | Languages |
|---|---|
| Concepticon only | 55 |
| WordNet only | 0 |
| Etymon only | 90 |
| Phonotacticon only | 325 |
| NoRaRe only | 0 |
| Concepticon ∩ WordNet | 509 |
| Concepticon ∩ Etymon | 298 |
| Concepticon ∩ Phonotacticon | 185 |
| Concepticon ∩ NoRaRe | 52 |
| WordNet ∩ Etymon | 282 |
| WordNet ∩ Phonotacticon | 178 |
| WordNet ∩ NoRaRe | 52 |
| Etymon ∩ Phonotacticon | 109 |
| Etymon ∩ NoRaRe | 49 |
| Phonotacticon ∩ NoRaRe | 34 |
| All three (excl. others) | 282 |
| All four (excl. NoRaRe) | 102 |
| All five datasets | 34 |

WordNet only = 0 because WordNet uses the same BabelNet identifier format as Concepticon, and every language in WordNet also appears in Concepticon. The 509-language WordNet ∩ Concepticon intersection covers the entire WordNet.

### Linking examples

The same language expressed in each dataset's identifier system, resolved to one languoid:

```
  Language               Canonical ID   Concepticon    WordNet        Etymon       Phonotacticon  NoRaRe

  Dutch                  lang:006448    NL             NL             nld          dutc1256       nl
  German                 lang:006636    DE             DE             deu          stan1295       de
  Turkish                lang:000917    TR             TR             tur          nucl1301       tr
  Russian                lang:006745    RU             RU             rus          russ1263       ru
  Japanese               lang:005185    JA             JA             jpn          nucl1643       ja
  Swahili                lang:001597    SW             SW             swa          -              sw
```
