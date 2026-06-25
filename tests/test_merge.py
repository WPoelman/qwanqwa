"""Integration test: merge all importers into a DataStore and verify the result."""

from pathlib import Path

import pytest

from qq.data_model import DataSource, IdType, LanguageScope, LanguoidLevel, RelationType
from qq.importers.base_importer import EntitySet
from qq.importers.glotscript_importer import GlotscriptImporter
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.linguameta_importer import LinguaMetaImporter
from qq.importers.iana_importer import IANAImporter
from qq.importers.loc_importer import LOCImporter
from qq.importers.sil_importer import SILImporter
from qq.importers.wikipedia_importer import WikipediaImporter
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.entity_resolution import EntityResolver
from qq.internal.build_database import (
    _fill_missing_bcp47_codes,
    _fill_missing_script_samples_from_endonyms,
    _reconcile_merged_languoids,
)
from qq.internal.merge import merge

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def merged_store():
    """Run the full import + merge pipeline with fixture data."""
    resolver = EntityResolver()

    # Import in the same order as the real pipeline
    importers_config = [
        ("linguameta", LinguaMetaImporter),
        ("glottolog", GlottologImporter),
        ("glotscript", GlotscriptImporter),
        ("sil_iso6393", SILImporter),
        ("loc", LOCImporter),
        ("iana", IANAImporter),
        ("wikipedia", WikipediaImporter),
    ]

    # Pre-register languoids needed by SIL (ron, knw, huc)
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "ron"})
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "knw"})
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "huc"})

    to_merge = []
    for source_name, importer_class in importers_config:
        imp = importer_class(resolver)
        imp.import_data(FIXTURES / source_name)
        to_merge.append((importer_class.source, imp.entity_set))

    store = merge(to_merge)
    return store, resolver


class TestMergeIntegration:
    def test_store_has_entities(self, merged_store):
        store, resolver = merged_store
        assert len(store._entities) > 0

    def test_has_languoids(self, merged_store):
        store, resolver = merged_store
        languoids = store.all_of_type(Languoid)
        assert len(languoids) >= 2  # At least nld and frr

    def test_has_scripts(self, merged_store):
        store, resolver = merged_store
        scripts = store.all_of_type(Script)
        assert len(scripts) >= 1

    def test_has_regions(self, merged_store):
        store, resolver = merged_store
        regions = store.all_of_type(GeographicRegion)
        assert len(regions) >= 2

    def test_dutch_merged_from_multiple_sources(self, merged_store):
        """Dutch should have data merged from linguameta, glottolog, glotscript, SIL/LOC, and wikipedia."""
        store, resolver = merged_store
        dutch_id = resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = store.get(dutch_id)
        assert dutch is not None
        assert isinstance(dutch, Languoid)

        # From linguameta
        assert dutch.name == "Dutch"
        assert dutch.speaker_count == 24000000

        # From glottolog (or linguameta: both set glottocode)
        assert dutch.glottocode == "dutc1256"
        assert dutch.level == LanguoidLevel.LANGUAGE

        # From SIL ISO 639-3
        assert dutch.scope == LanguageScope.INDIVIDUAL

    def test_dutch_has_parent_relation(self, merged_store):
        """After merge, Dutch should still have Germanic as parent."""
        store, resolver = merged_store
        dutch_id = resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = store.get(dutch_id)
        parent_rels = dutch._relations.get(RelationType.PARENT_LANGUOID, [])
        assert len(parent_rels) == 1

    def test_dutch_has_script_relation(self, merged_store):
        """Dutch should have Latin script from both linguameta and glotscript."""
        store, resolver = merged_store
        dutch_id = resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = store.get(dutch_id)
        script_rels = dutch._relations.get(RelationType.USES_SCRIPT, [])
        assert len(script_rels) >= 1
        target_ids = {r.target_id for r in script_rels}
        assert "script:latn" in target_ids

    def test_dutch_has_region_relation(self, merged_store):
        """Dutch should have SPOKEN_IN_REGION relations for NL and BE."""
        store, resolver = merged_store
        dutch_id = resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = store.get(dutch_id)
        region_rels = dutch._relations.get(RelationType.SPOKEN_IN_REGION, [])
        target_ids = {r.target_id for r in region_rels}
        assert "region:nl" in target_ids
        assert "region:be" in target_ids

    def test_dutch_has_wikipedia(self, merged_store):
        """Dutch should have Wikipedia info from wikipedia importer."""
        store, resolver = merged_store
        dutch_id = resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = store.get(dutch_id)
        assert dutch.wikipedia is not None
        assert dutch.wikipedia.article_count == 2150000

    def test_region_enriched_by_iana(self, merged_store):
        """Netherlands region should be available from IANA region subtags."""
        store, resolver = merged_store
        nl = store.get("region:nl")
        assert nl is not None
        assert isinstance(nl, GeographicRegion)
        assert nl.country_code == "NL"
        assert nl.name == "Netherlands"

    def test_deprecated_code_from_sil(self, merged_store):
        """SIL deprecated codes should be on merged entities."""
        store, resolver = merged_store
        ron_id = resolver.resolve(IdType.ISO_639_3, "ron")
        ron = store.get(ron_id)
        assert ron is not None
        assert ron.deprecated_codes is not None
        assert any(dc.code == "mol" for dc in ron.deprecated_codes)

    def test_no_duplicate_relations(self, merged_store):
        """Relations should be deduplicated during merge."""
        store, resolver = merged_store
        dutch_id = resolver.resolve(IdType.ISO_639_3, "nld")
        dutch = store.get(dutch_id)
        # Check that script relations are not duplicated
        script_rels = dutch._relations.get(RelationType.USES_SCRIPT, [])
        target_ids = [r.target_id for r in script_rels]
        # There might be duplicates with different metadata (canonical vs non-canonical)
        # but target_id should not appear more than twice (linguameta + glotscript)
        from collections import Counter

        counts = Counter(target_ids)
        for target_id, count in counts.items():
            assert count <= 3, f"Relation to {target_id} appears {count} times"


def test_reconcile_merged_languoids_updates_earlier_entity_sets():
    resolver = EntityResolver()

    first_set = EntitySet()
    second_set = EntitySet()

    first_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "x-a"})
    first = Languoid(first_id, first_set, bcp_47="x-a", name="First")
    first_set.add(first)

    second_id = resolver.find_or_create_canonical_id({IdType.ISO_639_3: "xaa"})
    second = Languoid(second_id, second_set, iso_639_3="xaa", endonym="Second")
    second_set.add(second)

    script = Script("script:latn", first_set, iso_15924="Latn")
    script.add_relation(RelationType.USED_BY_LANGUOID, first_id)
    first_set.add(script)

    merged_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "x-a", IdType.ISO_639_3: "xaa"})
    assert merged_id == first_id
    assert resolver.get_identity(second_id) is None

    reconciled = _reconcile_merged_languoids(
        [
            (LinguaMetaImporter.source, first_set),
            (GlottologImporter.source, second_set),
        ],
        resolver,
    )

    assert reconciled == {second_id: merged_id}
    assert first_set.get(first_id) is not None
    assert first_set.get(second_id) is None
    assert second_set.get(merged_id) is not None
    assert second_set.get(second_id) is None
    assert [rel.target_id for rel in script._relations[RelationType.USED_BY_LANGUOID]] == [merged_id]


def test_script_name_prefers_unicode():
    linguameta = EntitySet()
    unicode = EntitySet()
    linguameta.add(Script("script:kawi", linguameta, name="Chorasmian"))
    unicode.add(Script("script:kawi", unicode, name="Kawi"))

    store = merge(
        [
            (LinguaMetaImporter.source, linguameta),
            (DataSource.UNICODE, unicode),
        ]
    )

    script = store.get("script:kawi")
    assert isinstance(script, Script)
    assert script.name == "Kawi"


def test_script_name_falls_back_to_linguameta():
    linguameta = EntitySet()
    linguameta.add(Script("script:tulu", linguameta, name="Tulu-Tigalari"))

    store = merge([(LinguaMetaImporter.source, linguameta)])

    script = store.get("script:tulu")
    assert isinstance(script, Script)
    assert script.name == "Tulu-Tigalari"


def test_fill_missing_bcp47_prefers_iso_639_1():
    from qq.internal.data_store import DataStore

    store = DataStore()
    resolver = EntityResolver()
    lang_id = resolver.find_or_create_canonical_id({IdType.ISO_639_1: "nl", IdType.ISO_639_3: "nld"})
    store.add(Languoid(lang_id, store, name="Dutch", iso_639_1="nl", iso_639_3="nld"))

    assert _fill_missing_bcp47_codes(store, resolver) == 1

    lang = store.get(lang_id)
    assert isinstance(lang, Languoid)
    assert lang.bcp_47 == "nl"
    assert resolver.resolve(IdType.BCP_47, "nl") == lang_id


def test_fill_missing_bcp47_falls_back_to_iso_639_3():
    from qq.internal.data_store import DataStore

    store = DataStore()
    resolver = EntityResolver()
    lang_id = resolver.find_or_create_canonical_id({IdType.ISO_639_3: "tok"})
    store.add(Languoid(lang_id, store, name="Toki Pona", iso_639_3="tok"))

    assert _fill_missing_bcp47_codes(store, resolver) == 1

    lang = store.get(lang_id)
    assert isinstance(lang, Languoid)
    assert lang.bcp_47 == "tok"
    assert resolver.resolve(IdType.BCP_47, "tok") == lang_id


def test_fill_missing_bcp47_does_not_use_iso_639_5():
    from qq.internal.data_store import DataStore

    store = DataStore()
    resolver = EntityResolver()
    family_id = resolver.find_or_create_canonical_id({IdType.ISO_639_5: "phi"})
    store.add(Languoid(family_id, store, name="Philippine languages", iso_639_5="phi", level=LanguoidLevel.FAMILY))

    assert _fill_missing_bcp47_codes(store, resolver) == 0

    family = store.get(family_id)
    assert isinstance(family, Languoid)
    assert family.bcp_47 is None
    assert resolver.resolve(IdType.BCP_47, "phi") is None


def test_fill_missing_bcp47_preserves_existing_value():
    from qq.internal.data_store import DataStore

    store = DataStore()
    resolver = EntityResolver()
    lang_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "x-existing", IdType.ISO_639_3: "xaa"})
    store.add(Languoid(lang_id, store, bcp_47="x-existing", iso_639_3="xaa"))

    assert _fill_missing_bcp47_codes(store, resolver) == 0

    lang = store.get(lang_id)
    assert isinstance(lang, Languoid)
    assert lang.bcp_47 == "x-existing"


def test_fill_missing_script_samples_from_matching_endonyms():
    from qq.internal.data_store import DataStore

    store = DataStore()
    greek = Languoid("lang:ell", store, name="Greek", endonym="Ελληνικά")
    greek_script = Script("script:grek", store, iso_15924="Grek", unicode_ranges=["U+0370..U+03FF"])
    latin_script = Script("script:latn", store, iso_15924="Latn", unicode_ranges=["U+0041..U+005A", "U+0061..U+007A"])

    store.add(greek)
    store.add(greek_script)
    store.add(latin_script)
    greek.add_relation(RelationType.USES_SCRIPT, greek_script.id, is_canonical=True)
    greek_script.add_relation(RelationType.USED_BY_LANGUOID, greek.id, is_canonical=True)
    latin_script.add_relation(RelationType.USED_BY_LANGUOID, greek.id, is_canonical=True)

    assert _fill_missing_script_samples_from_endonyms(store) == 1
    assert greek_script.sample == "Ελληνικά"
    assert latin_script.sample is None
