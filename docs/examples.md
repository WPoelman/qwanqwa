# Full examples
## Languoid
Only `name_data` is truncated.

```python
Languoid(
    bcp_47_code='am',
    deprecated_bcp_47_code=None,
    iso_639_3_code='amh',
    iso_639_2b_code=None,
    glottocode='amha1245',
    wikidata_id='Q28244',
    wikipedia_id='am',
    total_population=36000000,
    language_scope=LanguageScope(
        source='LINGUAMETA-ISO_639',
        scope=<Scope.LANGUAGE: 'LANGUAGE'>,
    ),
    macrolanguage_bcp_47_code=None,
    individual_language_bcp_47_codes=None,
    endangerment_status=None,
    language_description=LanguageDescription(
        source='LINGUAMETA-WIKIDATA',
        description='Semitic language of Ethiopia',
    ),
    name_data={
        'ab': NameData(
            source='LINGUAMETA-CLDR',
            bcp_47_code='ab',
            name='амхар',
            is_canonical=True,
        ),
        'af': NameData(
            source='LINGUAMETA-CLDR',
            bcp_47_code='af',
            name='Amharies',
            is_canonical=True,
        ),
        'am': NameData(
            source='LINGUAMETA-GOOGLE_RESEARCH',
            bcp_47_code='am',
            name='አማርኛ',
            is_canonical=True,
        ),
        'en': NameData(
            source='LINGUAMETA-GOOGLE_RESEARCH',
            bcp_47_code='en',
            name='Amharic',
            is_canonical=True,
        ),
    },
    language_script_locale=[
        LanguageScriptLocale(
            script=Script(
                source='LINGUAMETA-GOOGLE_RESEARCH',
                iso_15924_code='Ethi',
                is_canonical=True,
                is_historical=None,
                is_religious=None,
                is_for_transliteration=None,
                is_for_accessibility=None,
                is_in_widespread_use=None,
                has_official_status=None,
                has_symbolic_value=None,
            ),
            locale=SimpleLocale(
                source='LINGUAMETA-GOOGLE_RESEARCH',
                iso_3166_code='et',
            ),
            speaker_data=SpeakerData(
                source='LINGUAMETA-CLDR',
                number_of_speakers=36000000,
            ),
            official_status=OfficialStatus(
                source='LINGUAMETA-CLDR',
                has_official_status=True,
                has_regional_official_status=None,
                has_de_facto_official_status=None,
            ),
            geolocation=Geolocation(
                source='LINGUAMETA-GOOGLE_RESEARCH',
                latitude=11.708182,
                longitude=39.543457,
            ),
        ),
        LanguageScriptLocale(
            script=Script(
                source='LINGUAMETA-GOOGLE_RESEARCH',
                iso_15924_code='Latn',
                is_canonical=False,
                is_historical=None,
                is_religious=None,
                is_for_transliteration=True,
                is_for_accessibility=None,
                is_in_widespread_use=None,
                has_official_status=None,
                has_symbolic_value=None,
            ),
            locale=SimpleLocale(
                source='LINGUAMETA-GOOGLE_RESEARCH',
                iso_3166_code='et',
            ),
            speaker_data=SpeakerData(
                source='LINGUAMETA-CLDR',
                number_of_speakers=36000000,
            ),
            official_status=None,
            geolocation=None,
        ),
    ],
    english_name='Amharic',
    endonym='አማርኛ',
    estimated_number_of_speakers=36000000,
    writing_systems=[
        'Brai',
        'Ethi',
        'Latn',
    ],
    locales=['ET'],
    cldr_official_status=[
        'Official [ET]',
    ],
    is_macrolanguage=False,
    endangerment_status_description=<Endangerment.SAFE: 'SAFE'>,
)
```
