import pytest

from qq.interface import Languoid, Script
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver
from qq.internal.storage import DataManager, StorageBackend, load_data


def make_minimal_store() -> tuple[DataStore, EntityResolver]:
    """Return a DataStore + EntityResolver with one Languoid and one Script."""
    from qq.data_model import IdType

    store = DataStore()
    resolver = EntityResolver()

    lang_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "nl", IdType.ISO_639_3: "nld"})
    lang = Languoid(lang_id, store, name="Dutch", bcp_47="nl", iso_639_3="nld", speaker_count=24_000_000)
    store.add(lang)

    script = Script("script:0001", store)
    store.add(script)

    return store, resolver


def make_store_with_deprecated() -> tuple[DataStore, EntityResolver]:
    """Return a store with a deprecated code registered."""
    from qq.data_model import IdType

    store = DataStore()
    resolver = EntityResolver()

    lang_id = resolver.find_or_create_canonical_id({IdType.ISO_639_3: "ron"})
    lang = Languoid(lang_id, store, name="Romanian", iso_639_3="ron")
    store.add(lang)

    resolver.register_alias(IdType.ISO_639_3, "mol", lang_id)
    resolver.register_deprecated(IdType.ISO_639_3, "mol", "merged")

    return store, resolver


class TestStorageBackendABC:
    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]


class TestStorageRoundTrip:
    @pytest.mark.parametrize("fmt", ["json", "json.gz", "pkl.gz"])
    def test_entities_survive_roundtrip(self, tmp_path, fmt):
        store, resolver = make_minimal_store()
        output = tmp_path / f"db.{fmt}"

        manager = DataManager(fmt)
        manager.save_dataset(store, output, resolver)

        loaded_store, _ = manager.load_dataset(output)
        assert len(loaded_store._entities) == len(store._entities)

        lang = next(
            (e for e in loaded_store._entities.values() if isinstance(e, Languoid)),
            None,
        )
        assert lang is not None
        assert lang.name == "Dutch"
        assert lang.bcp_47 == "nl"
        assert lang.iso_639_3 == "nld"
        assert lang.speaker_count == 24_000_000

    @pytest.mark.parametrize("fmt", ["json", "json.gz", "pkl.gz"])
    def test_resolver_survives_roundtrip(self, tmp_path, fmt):
        from qq.data_model import IdType

        store, resolver = make_minimal_store()
        output = tmp_path / f"db.{fmt}"

        manager = DataManager(fmt)
        manager.save_dataset(store, output, resolver)

        _, loaded_resolver = manager.load_dataset(output)
        assert loaded_resolver.resolve(IdType.BCP_47, "nl") is not None
        assert loaded_resolver.resolve(IdType.ISO_639_3, "nld") is not None

    @pytest.mark.parametrize("fmt", ["json", "json.gz", "pkl.gz"])
    def test_deprecated_codes_survive(self, tmp_path, fmt):
        from qq.data_model import IdType

        store, resolver = make_store_with_deprecated()
        output = tmp_path / f"db.{fmt}"

        manager = DataManager(fmt)
        manager.save_dataset(store, output, resolver)

        _, loaded_resolver = manager.load_dataset(output)
        assert loaded_resolver.is_deprecated(IdType.ISO_639_3, "mol")

    def test_load_data_detects_format(self, tmp_path):
        """load_data() auto-selects backend from file extension."""
        from qq.data_model import IdType

        store, resolver = make_minimal_store()

        for fmt, suffix in [("json.gz", "db.json.gz"), ("pkl.gz", "db.pkl.gz"), ("json", "db.json")]:
            output = tmp_path / suffix
            DataManager(fmt).save_dataset(store, output, resolver)
            loaded_store, loaded_resolver = load_data(output)
            assert len(loaded_store._entities) == len(store._entities)
            assert loaded_resolver.resolve(IdType.BCP_47, "nl") is not None
