"""Tests for DataValidator."""

import pytest

from qq.data_model import IdType, RelationType
from qq.interface import Languoid
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver
from qq.internal.validation import DataValidator


def make_validator(store: DataStore, resolver: EntityResolver) -> DataValidator:
    return DataValidator(store, resolver)


def basic_store_and_resolver() -> tuple[DataStore, EntityResolver]:
    """One registered Dutch languoid, nothing broken."""
    store = DataStore()
    resolver = EntityResolver()

    lang_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "nl", IdType.ISO_639_3: "nld"})
    lang = Languoid(lang_id, store, name="Dutch", bcp_47="nl", iso_639_3="nld")
    store.add(lang)

    return store, resolver


class TestDataValidator:
    def test_orphaned_entity_detected(self):
        """A Languoid with no resolver identity should appear in orphaned_entities."""
        store = DataStore()
        resolver = EntityResolver()

        # Add entity to store but do NOT register it in the resolver
        lang = Languoid("lang:orphan", store, name="Ghost")
        store.add(lang)

        validator = make_validator(store, resolver)
        orphans = validator.find_orphaned_entities()
        assert "lang:orphan" in orphans

    def test_broken_relation_detected(self):
        """A relation pointing to a non-existent entity should be flagged."""
        store = DataStore()
        resolver = EntityResolver()

        lang_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "nl"})
        lang = Languoid(lang_id, store, name="Dutch", bcp_47="nl")
        store.add(lang)

        # Add a relation to a target that doesn't exist
        lang.add_relation(RelationType.USES_SCRIPT, "script:missing")

        validator = make_validator(store, resolver)
        broken = validator.find_broken_relations()
        assert len(broken) == 1
        assert broken[0]["target_id"] == "script:missing"

    def test_duplicate_identifiers_detected(self):
        """Two Languoids sharing the same ISO 639-3 code in their identities are reported."""
        store = DataStore()
        resolver = EntityResolver()

        id1 = resolver.find_or_create_canonical_id({IdType.ISO_639_3: "nld"})
        lang1 = Languoid(id1, store, name="Dutch", iso_639_3="nld")
        store.add(lang1)

        # Create a second entity with a different BCP-47 code, then manually
        # inject the same ISO 639-3 into its identity to simulate a data error.
        id2 = resolver.find_or_create_canonical_id({IdType.BCP_47: "nl-alt"})
        lang2 = Languoid(id2, store, name="Dutch Alt", iso_639_3="nld")
        store.add(lang2)
        identity2 = resolver.get_identity(id2)
        assert identity2
        identity2.identifiers[IdType.ISO_639_3] = "nld"

        validator = make_validator(store, resolver)
        duplicates = validator.find_duplicate_identifiers()
        assert "iso_639_3" in duplicates
        assert any(value == "nld" for value, _ in duplicates["iso_639_3"])

    def test_check_data_completeness_counts(self):
        """Percentages should be arithmetically correct."""
        store = DataStore()
        resolver = EntityResolver()

        id1 = resolver.find_or_create_canonical_id({IdType.BCP_47: "nl"})
        lang1 = Languoid(id1, store, name="Dutch", bcp_47="nl")
        store.add(lang1)

        id2 = resolver.find_or_create_canonical_id({IdType.BCP_47: "fr"})
        lang2 = Languoid(id2, store, name=None, bcp_47="fr")
        store.add(lang2)

        validator = make_validator(store, resolver)
        completeness = validator.check_data_completeness()

        # 1 out of 2 has a name -> 50%
        assert completeness["has_name"] == pytest.approx(50.0)
        # Both have bcp_47 -> 100%
        assert completeness["has_bcp_47"] == pytest.approx(100.0)

    def test_validate_all_returns_structure(self):
        """validate_all() should return a dict with all expected keys without crashing."""
        store, resolver = basic_store_and_resolver()
        validator = make_validator(store, resolver)
        results = validator.validate_all()

        expected_keys = {
            "total_entities",
            "orphaned_entities",
            "missing_critical_ids",
            "duplicate_identifiers",
            "broken_relations",
            "data_completeness",
        }
        assert expected_keys == set(results.keys())
        assert results["total_entities"] == 1
        assert results["orphaned_entities"] == []
        assert results["broken_relations"] == []
