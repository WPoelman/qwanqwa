# QQ (QwanQua): Language Metadata
This is a language metadata toolkit to make it easier to work with a large variety of metadata from a single interface.
Currently this metadata includes:

* Identifiers and related information: `iso-639-3`, `bcp-47`, Glottocode, Wikidata, Wikipedia
* Geographic information
* Speaker information
* Writing systems
* Names

Planned:
* Phylogenetic information
* Additional identifiers
* Linking with [CLLD](https://github.com/clld) datasets
* Typological features: `grambank`, `wals`, `uriel`
* A graph-based view to traverse between languoids (family trees, geo areas, shared features etc.)

## Languoids
In `qq`, language-like entities as referred to as [*Languoids*](http://www.glottopedia.de/index.php/Languoid), since it includes dialects, macro-languages and language areas.
Not all languoids have coverage for all features.

Number of languoids: 7511


## Usage
```
pip install git+https://github.com/WPoelman/qq
```

**Important**: `qq` makes a strict distinction between `None` (*don't know*) and `False` (*it is not the case*). Make sure to keep this in mind when checking boolean values for truthiness, so avoid `if not script.is_canonical:`, but instead explicitly check `if script.is_canonical is None:` if you're interested in missing values for example.

```python
from qq.linguameta import LinguaMeta, LanguoidID

# Load from the pre-compiled database
lm = LinguaMeta.from_db()

# Access Languoid info using whatever ID you have
nl1 = lm.get('nl', key_type=LanguoidID.BCP_47)
nl2 = lm.get('nld', key_type=LanguoidID.ISO_639_3)

# This will give the same Languoid
assert nl1 == nl2
> True

am = lm.get('am') # Default key_type is BCP_47

# Language identifiers
am.iso_639_3_code
> 'amh'
am.glottocode
> 'amha1245'
am.wikidata_id
> 'Q28244',
am.wikipedia_id
> 'am'

# Names in different languages
am.endonym
> 'አማርኛ'
am.name_data['fr'].name
> 'amharique'

# English description
am.language_description.description
> 'Semitic language of Ethiopia'

# Endangerment status
am.endangerment_status
> <Endangerment.SAFE: 'SAFE'>

# Scripts
am.canonical_scripts
> [
    Script(
        iso_15924_code='ethi',
        is_canonical=True,
        is_historical=None,
        is_religious=None,
        is_for_transliteration=None,
        is_for_accessibility=None,
        is_in_widespread_use=None,
        has_official_status=None,
        has_symbolic_value=None,
        source='GOOGLE_RESEARCH',
    )
]

# Mapping between codes
dir(lm.id_mapping)
> [
    'bcp2glottocode',
    'bcp2iso_639_2b_code',
    'bcp2iso_639_3_code',
    'bcp2wikidata',
    'bcp2wikipedia',
    'glottocode2bcp',
    'iso_639_2b_code2bcp',
    'iso_639_3_code2bcp',
    'wikidata2bcp',
    'wikipedia2bcp',
    ...
]
```

... and more, [here](docs/example.md) are some full examples.

## Sources
### LinguaMeta
* Paper: https://aclanthology.org/2024.lrec-main.921/
* Github: https://github.com/google-research/url-nlp/tree/main/linguameta
* License: CC BY-SA 4.0

Individual sources (taken from LinguaMeta README):
| JSON value          | Source                                | License type      | Link                                                                                |
| ------------------- | ------------------------------------- | ----------------- | ----------------------------------------------------------------------------------- |
| ``CLDR``            | Unicode CLDR                          | non-standard      | [License](https://www.unicode.org/license.txt)                                      |
| ``GLOTTOLOG``       | Glottolog                             | CC BY 4.0         | [Site homepage](https://glottolog.org/)                                             |
| ``GOOGLE_RESEARCH`` | Language research conducted at Google | CC BY 4.0         | [License](https://github.com/google-research/url-nlp/blob/main/LICENSE)             |
| ``IETF``            | IETF                                  | CC BY 4.0         | [License](https://trustee.ietf.org/assets/the-ietf-trusts-copyrights-and-licenses/) |
| ``ISO_639``         | SIL ISO 639 Registration Authority    | non-standard      | [Terms of use](https://iso639-3.sil.org/code_tables/download_tables#termsofuse)     |
| ``WIKIDATA``        | Wikidata                              | CC0, CC BY-SA 3.0 | [Copyright info](https://www.wikidata.org/wiki/Wikidata:Copyright)                  |
| ``WIKIPEDIA``       | Wikipedia                             | CC BY-SA 4.0      | [Copyright info](https://en.wikipedia.org/wiki/Wikipedia:Copyrights)                |
| ``WIKTIONARY``      | Wiktionary                            | CC BY-SA 4.0      | [Copyright info](https://en.wiktionary.org/wiki/Wiktionary:Copyrights)              |

### Wikipedia
* Source: https://meta.wikimedia.org/wiki/List_of_Wikipedias
* License: CC BY-SA 4.0

## Name
**Q**wan**q**wa is a phonetic spelling of 'ቋንቋ', which means *language* in Amharic.

## License
CC BY-SA 4.0
