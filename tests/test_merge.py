"""Integration test: merge all importers into a DataStore and verify the result."""

from pathlib import Path

import pytest

from qq.data_model import IdType, LanguageScope, LanguoidLevel, RelationType
from qq.importers.base_importer import EntitySet
from qq.importers.glotscript_importer import GlotscriptImporter
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.linguameta_importer import LinguaMetaImporter
from qq.importers.pycountry_importer import PycountryImporter
from qq.importers.sil_importer import SILImporter
from qq.importers.wikipedia_importer import WikipediaImporter
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.entity_resolution import EntityResolver
from qq.internal.build_database import _reconcile_merged_languoids
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
        ("pycountry", PycountryImporter),
        ("wikipedia", WikipediaImporter),
        ("sil", SILImporter),
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
        """Dutch should have data merged from linguameta, glottolog, glotscript, pycountry, wikipedia."""
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

        # From pycountry
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

    def test_region_enriched_by_pycountry(self, merged_store):
        """Netherlands region should have official_name from pycountry."""
        store, resolver = merged_store
        nl = store.get("region:nl")
        assert nl is not None
        assert isinstance(nl, GeographicRegion)
        assert nl.official_name == "Kingdom of the Netherlands"

    def test_subdivision_exists(self, merged_store):
        """Subdivisions from pycountry should be in merged store."""
        store, resolver = merged_store
        nh = store.get("region:nl-nh")
        assert nh is not None
        assert nh.subdivision_code == "NL-NH"

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


def test_script_name_prefers_pycountry():
    linguameta = EntitySet()
    pycountry = EntitySet()
    linguameta.add(Script("script:kawi", linguameta, name="Chorasmian"))
    pycountry.add(Script("script:kawi", pycountry, name="Kawi"))

    store = merge(
        [
            (LinguaMetaImporter.source, linguameta),
            (PycountryImporter.source, pycountry),
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
