import pytest

from qq.access import Database
from qq.data_model import IdType
from qq.interface import Languoid, Script
from qq.internal.data_store import DataStore


def make_store_with_entities() -> tuple[DataStore, Languoid, Script]:
    """Return a DataStore pre-populated with one Languoid and one Script."""
    store = DataStore()
    lang = Languoid("lang:000001", store, name="Dutch", bcp_47="nl", speaker_count=24_000_000)
    script = Script("script:0001", store)
    store.add(lang)
    store.add(script)
    return store, lang, script


class TestDataStore:
    def test_add_and_get(self):
        store, lang, _ = make_store_with_entities()
        result = store.get("lang:000001")
        assert result is lang

    def test_get_missing(self):
        store = DataStore()
        assert store.get("lang:999999") is None

    def test_type_index(self):
        store, lang, script = make_store_with_entities()
        languoids = store.all_of_type(Languoid)
        scripts = store.all_of_type(Script)
        assert len(languoids) == 1
        assert languoids[0] is lang
        assert len(scripts) == 1
        assert scripts[0] is script

    def test_query_exact_match(self):
        store, lang, _ = make_store_with_entities()
        results = store.query(Languoid, bcp_47="nl")
        assert len(results) == 1
        assert results[0] is lang

    def test_query_callable(self):
        store, lang, _ = make_store_with_entities()
        results = store.query(Languoid, speaker_count=lambda x: x > 1_000_000)
        assert len(results) == 1
        assert results[0] is lang

    def test_query_none_skipped(self):
        """Callable filters should not be called when the attribute is None."""
        store = DataStore()
        lang = Languoid("lang:000001", store, name="Test", speaker_count=None)
        store.add(lang)

        called_with = []

        def probe(x):
            called_with.append(x)
            return True

        results = store.query(Languoid, speaker_count=probe)
        # speaker_count is None, so probe should not have been called and
        # the entity should NOT be included.
        assert called_with == []
        assert results == []

    def test_query_no_match(self):
        store, _, _ = make_store_with_entities()
        results = store.query(Languoid, bcp_47="zz")
        assert results == []

    def test_query_no_filters(self):
        store, lang, script = make_store_with_entities()
        languoids = store.query(Languoid)
        assert len(languoids) == 1
        # Without type filter, both entity types are returned
        all_entities = store.query()
        assert len(all_entities) == 2


@pytest.fixture(scope="module")
def loaded_access():
    """Load a real Database from the packaged database."""
    return Database.load()


@pytest.fixture(scope="module")
def name_cache(loaded_access):
    """Return the NameDataCache attached to the loaded access."""
    cache = loaded_access.store.name_cache
    if cache is None:
        pytest.skip("names.zip not available: skipping NameDataCache tests")
    return cache


@pytest.fixture(scope="module")
def dutch_canonical(loaded_access):
    """Canonical ID for Dutch in the packaged database."""
    canonical = loaded_access.resolver.resolve(IdType.BCP_47, "nl")
    if canonical is None:
        pytest.skip("Dutch not found in database")
    return canonical


class TestNameDataCache:
    def test_get_returns_name_data(self, name_cache, dutch_canonical):
        data = name_cache.get(dutch_canonical)
        assert data is not None
        assert len(data) > 0

    def test_get_caches_result(self, name_cache, dutch_canonical):
        first = name_cache.get(dutch_canonical)
        second = name_cache.get(dutch_canonical)
        assert first is second

    def test_get_unknown_id(self, name_cache):
        result = name_cache.get("lang:999999")
        assert result is None

    def test_get_name_in_by_canonical(self, name_cache, loaded_access, dutch_canonical):
        en_canonical = loaded_access.resolver.resolve(IdType.BCP_47, "en")
        if en_canonical is None:
            pytest.skip("English not in database")
        name = name_cache.get_name_in(dutch_canonical, en_canonical)
        assert name is not None
        assert isinstance(name, str)

    def test_get_name_in_by_bcp47(self, name_cache, dutch_canonical):
        name = name_cache.get_name_in(dutch_canonical, "en")
        assert name is not None
        assert isinstance(name, str)

    def test_get_name_in_missing(self, name_cache, dutch_canonical):
        result = name_cache.get_name_in(dutch_canonical, "zz-ZZ")
        assert result is None

    def test_preload(self, name_cache, dutch_canonical):
        name_cache.clear_cache()
        name_cache.preload([dutch_canonical])
        assert dutch_canonical in name_cache._cache
