from qq.data_model import NameEntry
from qq.internal.names_merge import merge_name_data


def _entry(name, bcp_47_code="en", is_canonical=False):
    return NameEntry(name=name, bcp_47_code=bcp_47_code, is_canonical=is_canonical)


class TestMergeNameData:
    def test_empty_input(self):
        assert merge_name_data([]) == {}

    def test_single_source(self):
        source = {"lang:001": [_entry("Dutch", is_canonical=True)]}
        result = merge_name_data([source])
        assert len(result) == 1
        assert len(result["lang:001"]) == 1
        assert result["lang:001"][0].name == "Dutch"
        assert result["lang:001"][0].is_canonical is True

    def test_merge_disjoint_languoids(self):
        source_a = {"lang:001": [_entry("Dutch")]}
        source_b = {"lang:002": [_entry("French")]}
        result = merge_name_data([source_a, source_b])
        assert "lang:001" in result
        assert "lang:002" in result

    def test_merge_same_languoid_different_names(self):
        source_a = {"lang:001": [_entry("Dutch")]}
        source_b = {"lang:001": [_entry("Nederlands", bcp_47_code="nl")]}
        result = merge_name_data([source_a, source_b])
        assert len(result["lang:001"]) == 2

    def test_dedup_same_name_same_locale(self):
        source_a = {"lang:001": [_entry("Dutch")]}
        source_b = {"lang:001": [_entry("Dutch")]}
        result = merge_name_data([source_a, source_b])
        assert len(result["lang:001"]) == 1

    def test_dedup_prefers_canonical(self):
        source_a = {"lang:001": [_entry("Dutch", is_canonical=False)]}
        source_b = {"lang:001": [_entry("Dutch", is_canonical=True)]}
        result = merge_name_data([source_a, source_b])
        assert len(result["lang:001"]) == 1
        assert result["lang:001"][0].is_canonical is True

    def test_dedup_keeps_canonical_when_first(self):
        source_a = {"lang:001": [_entry("Dutch", is_canonical=True)]}
        source_b = {"lang:001": [_entry("Dutch", is_canonical=False)]}
        result = merge_name_data([source_a, source_b])
        assert len(result["lang:001"]) == 1
        assert result["lang:001"][0].is_canonical is True

    def test_multiple_sources_complex(self):
        linguameta = {
            "lang:001": [
                _entry("Dutch", is_canonical=True),
                _entry("Nederlands", bcp_47_code="nl", is_canonical=True),
            ]
        }
        glottolog = {
            "lang:001": [_entry("Dutch", is_canonical=True)],
            "lang:002": [_entry("Afrikaans", is_canonical=True)],
        }
        wikipedia = {
            "lang:001": [
                _entry("Dutch", is_canonical=False),
                _entry("Nederlands", bcp_47_code="nl", is_canonical=False),
            ]
        }
        result = merge_name_data([linguameta, glottolog, wikipedia])

        # lang:001: Dutch(en) deduped to canonical, Nederlands(nl) deduped to canonical
        assert len(result["lang:001"]) == 2
        en_entry = [e for e in result["lang:001"] if e.bcp_47_code == "en"][0]
        assert en_entry.is_canonical is True
        nl_entry = [e for e in result["lang:001"] if e.bcp_47_code == "nl"][0]
        assert nl_entry.is_canonical is True

        # lang:002 only from glottolog
        assert len(result["lang:002"]) == 1

    def test_empty_name_data_dicts(self):
        result = merge_name_data([{}, {}, {}])
        assert result == {}

    def test_same_name_different_locales_kept(self):
        """Same name string in different locales should not be deduped."""
        source = {
            "lang:001": [
                _entry("Dutch", bcp_47_code="en"),
                _entry("Dutch", bcp_47_code="de"),
            ]
        }
        result = merge_name_data([source])
        assert len(result["lang:001"]) == 2
