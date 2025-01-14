# Qwanqwa (`qq`): Language Metadata
This is a language metadata toolkit to make it easier to work with a large variety of metadata from a single interface.
Currently this metadata includes:

* Official identifiers: `iso-639-3`, `bcp-47`, Glottocode, Wikidata, Wikipedia
* Non-official identifiers: NLLB-style codes (`zho_Hans`, `zho_Hant`, etc.)[^1]
* Geographic information
* Speaker information
* Writing systems
* Names

Planned:
* Phylogenetic information
* Linking with [CLLD](https://github.com/clld) datasets
* Typological features: `grambank`, `wals`, `uriel`
* A graph-based view to traverse between languoids (family trees, geo areas, shared features etc.)

**Name**: **Q**wan**q**wa is a phonetic spelling of 'ቋንቋ', which means *language* in Amharic; `qq` is nice and short to type.

## Languoids
In `qq`, language-like entities as referred to as [*Languoids*](http://www.glottopedia.de/index.php/Languoid), since it includes dialects, macro-languages and language areas.
Not all languoids have coverage for all features.

Number of languoids: 7511


## Usage
```
pip install git+https://github.com/WPoelman/qwanqwa
```

**Important**: `qq` makes a strict distinction between `None` (*don't know*) and `False` (*it is not the case*). Make sure to keep this in mind when checking boolean values for truthiness, so if you're interested in missing values for example, avoid `if not script.is_canonical:`, but instead explicitly check `if script.is_canonical is None:`.

```python
from qq import LanguageData, TagType

# Load from the pre-compiled database
ld = LanguageData.from_db()

# Access Languoid info using whatever official tag you have
nl1 = ld.get('nl', tag_type=TagType.BCP_47_CODE)
nl2 = ld.get('nld', tag_type=TagType.ISO_639_3_CODE)
# The `guess` method tries all known official tag types,
# be careful though since this can give unexpected resutls.
nl3 = ld.guess('dut')  # happens to be TagType.ISO_639_2_B

# In this case, these will give the same Languoid
assert nl1 == nl2 == nl3
> True

am = ld.get('am') # Default tag_type is BCP_47

# Language identifiers
am.iso_639_3_code
> 'amh'
am.glottocode
> 'amha1245'
am.wikidata_id
> 'Q28244',
am.wikipedia_id
> 'am'

# Also some non-standard identifiers, often used in NLP research
am.nllb_style_codes_iso_639_3
> ['amh_Ethi']
am.nllb_style_codes_bcp_47
> ['am_Ethi']

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
dir(ld.tag_conversion)
> [
    'bcp_47_code2glottocode',
    'bcp_47_code2iso_639_2b_code',
    'bcp_47_code2iso_639_3_code',
    'bcp_47_code2wikidata_id',
    'bcp_47_code2wikipedia_id',
    'glottocode2bcp_47_code',
    'glottocode2iso_639_2b_code',
    'glottocode2iso_639_3_code',
    'glottocode2wikidata_id',
    'glottocode2wikipedia_id',
    'iso_639_2b_code2bcp_47_code',
    'iso_639_2b_code2glottocode',
    'iso_639_2b_code2iso_639_3_code',
    'iso_639_2b_code2wikidata_id',
    'iso_639_2b_code2wikipedia_id',
    'iso_639_3_code2bcp_47_code',
    'iso_639_3_code2glottocode',
    'iso_639_3_code2iso_639_2b_code',
    ...
]
```

... and more, [here](docs/example.md) are some full examples.

[^1]: This is a combination of an `iso-693-3` or `bcp-47` language tag and `iso-15924` script tag. This is similar to the first parts of an [IETF Tag](https://en.wikipedia.org/wiki/IETF_language_tag), which, confusingly, can also be referred to as a `bcp-47` tag on its own. This is done in NLLB for instance. This is not wrong, but because data in `qq` is based on LinguaMeta, who interpret just the first part of a IETF tag to be a `bcp-47` tag, we're sticking to  LinguaMeta's interpretation of `bcp-47` and refer to the combined tag as `nllb_style`. The `iso-15924` part of the `nllb_style` tags are based on Glotscript, excluding Braille.

## Sources
### LinguaMeta
* Paper: https://aclanthology.org/2024.lrec-main.921/
* Github: https://github.com/google-research/url-nlp/tree/main/linguameta
* License: CC BY-SA 4.0

Individual sources (taken from LinguaMeta [README](https://github.com/google-research/url-nlp/blob/main/linguameta/README.md)):
| LinguaMeta ID       | Source                                | License type      | Link                                                                                |
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

### GlotScript
* Paper: https://aclanthology.org/2024.lrec-main.687/
* Github: https://github.com/cisnlp/GlotScript
* License: CC BY-SA 4.0

Individual sources (taken from GlotScript [README](https://github.com/cisnlp/GlotScript/blob/main/metadata/README.md)):
- [Wikipedia](https://en.wikipedia.org/wiki/ISO_639:xxx): Since Wikipedia writing system metadata is not easily redistributed, we provide our crawled version of the Writing System Text from Wikipedia in the [sources folder](https://github.com/cisnlp/GlotScript/blob/main/metadata/sources/wikipedia.csv).
- [ScriptSource](https://scriptsource.org/)
- [Unicode CLDR](https://github.com/unicode-org/cldr-json/blob/main/cldr-json/cldr-core/supplemental/likelySubtags.json)
- [LangTag](https://raw.githubusercontent.com/silnrsi/langtags/master/pub/langtags.json)
- [LREC_2800](https://raw.githubusercontent.com/google-research/url-nlp/main/language_metadata/data.tsv)
- [Omniglot](https://www.omniglot.com/writing/langalph.htm)

## License
CC BY-SA 4.0
