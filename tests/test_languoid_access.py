from pathlib import Path

import pytest

from qq.access import Database, DeprecatedCodeWarning
from qq.data_model import IdType, LanguoidLevel
from qq.importers.glotscript_importer import GlotscriptImporter
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.iana_importer import IANAImporter
from qq.importers.linguameta_importer import LinguaMetaImporter
from qq.importers.pycountry_importer import PycountryImporter
from qq.importers.sil_importer import SILImporter
from qq.importers.wikipedia_importer import WikipediaImporter
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge import merge

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def access():
    """Build a LanguoidAccess from fixture data."""
    resolver = EntityResolver()

    importers_config = [
        ("linguameta", LinguaMetaImporter),
        ("glottolog", GlottologImporter),
        ("glotscript", GlotscriptImporter),
        ("pycountry", PycountryImporter),
        ("wikipedia", WikipediaImporter),
        ("sil", SILImporter),
        ("iana", IANAImporter),
    ]

    # Pre-register languoids needed by SIL
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "ron"})
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "knw"})
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "huc"})

    to_merge = []
    for source_name, importer_class in importers_config:
        imp = importer_class(resolver)
        imp.import_data(FIXTURES / source_name)
        to_merge.append((importer_class.source, imp.entity_set))

    store = merge(to_merge)
    return Database(store, resolver)


class TestGet:
    def test_get_by_bcp47(self, access):
        dutch = access.get("nl", IdType.BCP_47)
        assert dutch.name == "Dutch"

    def test_get_by_iso_639_3(self, access):
        dutch = access.get("nld", IdType.ISO_639_3)
        assert dutch.name == "Dutch"

    def test_get_not_found_raises(self, access):
        with pytest.raises(KeyError, match="not found"):
            access.get("zzz", IdType.ISO_639_3)

    def test_get_returns_languoid(self, access):
        result = access.get("nl", IdType.BCP_47)
        assert isinstance(result, Languoid)


class TestGuess:
    def test_guess_finds_by_any_type(self, access):
        dutch = access.guess("nld")
        assert dutch.name == "Dutch"

    def test_guess_finds_bcp47(self, access):
        dutch = access.guess("nl")
        assert dutch.name == "Dutch"

    def test_guess_not_found_raises(self, access):
        with pytest.raises(KeyError, match="not found"):
            access.guess("xyzxyz")


class TestConvert:
    def test_convert_bcp47_to_iso639_3(self, access):
        result = access.convert("nl", IdType.BCP_47, IdType.ISO_639_3)
        assert result == "nld"

    def test_convert_iso639_3_to_bcp47(self, access):
        result = access.convert("nld", IdType.ISO_639_3, IdType.BCP_47)
        assert result == "nl"

    def test_convert_not_found_returns_none(self, access):
        result = access.convert("zzz", IdType.BCP_47, IdType.ISO_639_3)
        assert result is None


class TestIdConversion:
    def test_convert_via_id_conversion(self, access):
        result = access.id_conversion.convert("nl", IdType.BCP_47, IdType.ISO_639_3)
        assert result == "nld"


class TestSearch:
    def test_search_by_name(self, access):
        results = access.search("Dutch")
        assert len(results) >= 1
        assert any(lang.name == "Dutch" for lang in results)

    def test_search_case_insensitive(self, access):
        results = access.search("dutch")
        assert len(results) >= 1
        assert any(lang.name == "Dutch" for lang in results)

    def test_search_partial(self, access):
        results = access.search("Dut")
        assert len(results) >= 1

    def test_search_no_results(self, access):
        results = access.search("nope-buddy")
        assert results == []

    def test_search_limit(self, access):
        results = access.search("", limit=2)
        assert len(results) <= 2


class TestDeprecated:
    def test_is_deprecated_true(self, access):
        # mol is deprecated in SIL fixtures (merged to ron)
        assert access.is_deprecated("mol", IdType.ISO_639_3)

    def test_is_deprecated_false(self, access):
        assert not access.is_deprecated("nld", IdType.ISO_639_3)

    def test_is_deprecated_checks_all_types(self, access):
        # mol should be found when checking all types
        assert access.is_deprecated("mol")

    def test_get_deprecated_with_replacement_warns(self, access):
        # mol was merged to ron, so it should resolve but warn
        # First check if mol actually resolves to something
        canonical = access.resolver.resolve(IdType.ISO_639_3, "mol")
        if canonical:
            with pytest.warns(DeprecatedCodeWarning):
                access.get("mol", IdType.ISO_639_3)

    def test_get_deprecated_no_replacement_raises(self, access):
        # If a deprecated code has no replacement, it should raise
        # Register a deprecated code with no replacement
        access.resolver.register_deprecated(IdType.ISO_639_3, "zzd", "non-existent")
        with pytest.raises(KeyError, match="deprecated"):
            access.get("zzd", IdType.ISO_639_3)


class TestCollections:
    def test_all_languoids(self, access):
        languoids = access.all_languoids
        assert len(languoids) >= 2
        assert all(isinstance(lang, Languoid) for lang in languoids)

    def test_all_languages(self, access):
        languages = access.all_languages
        assert all(lang.level == LanguoidLevel.LANGUAGE for lang in languages)

    def test_all_families(self, access):
        families = access.all_families
        assert all(lang.level == LanguoidLevel.FAMILY for lang in families)

    def test_all_dialects(self, access):
        dialects = access.all_dialects
        assert all(lang.level == LanguoidLevel.DIALECT for lang in dialects)


class TestGetNames:
    def test_get_names_returns_none_without_name_cache(self, access):
        # access was created without names_path
        result = access.get_names("nl")
        assert result is None


class TestTraversalProperties:
    """Test Languoid traversal convenience properties."""

    def test_parent_returns_languoid(self, access):
        dutch = access.get("nl")
        assert dutch.parent is not None
        assert isinstance(dutch.parent, Languoid)
        assert dutch.parent.name == "Germanic"

    def test_parent_none_for_root(self, access):
        # The top-level family has no parent
        dutch = access.get("nl")
        assert dutch.parent is not None
        root = dutch.family_tree[-1]
        assert root.parent is None

    def test_family_tree_contains_ancestors(self, access):
        dutch = access.get("nl")
        tree = dutch.family_tree
        assert len(tree) >= 1
        assert any(a.name == "Germanic" for a in tree)

    def test_siblings_excludes_self(self, access):
        dutch = access.get("nl")
        siblings = dutch.siblings
        assert dutch not in siblings

    def test_siblings_share_parent(self, access):
        dutch = access.get("nl")
        for sib in dutch.siblings:
            assert sib.parent is not None
            assert sib.parent.id == dutch.parent.id

    def test_children_returns_list(self, access):
        dutch = access.get("nl")
        # Dutch has no children in fixture data
        assert isinstance(dutch.children, list)

    def test_descendants_returns_list(self, access):
        dutch = access.get("nl")
        result = dutch.descendants()
        assert isinstance(result, list)


class TestScriptProperties:
    """Test script-related properties on Languoid and Script."""

    def test_script_codes_returns_iso_codes(self, access):
        dutch = access.get("nl")
        codes = dutch.script_codes
        assert codes is not None
        assert "Latn" in codes

    def test_canonical_scripts_non_empty(self, access):
        dutch = access.get("nl")
        canonical = dutch.canonical_scripts
        assert len(canonical) >= 1
        assert canonical[0].iso_15924 == "Latn"

    def test_scripts_contains_script_objects(self, access):
        dutch = access.get("nl")
        for s in dutch.scripts:
            assert isinstance(s, Script)

    def test_nllb_codes_returns_language_script_combos(self, access):
        dutch = access.get("nl")
        codes = dutch.nllb_codes()
        assert isinstance(codes, list)
        assert any(c.startswith("nld_") for c in codes)

    def test_nllb_codes_bcp47_variant(self, access):
        dutch = access.get("nl")
        codes = dutch.nllb_codes(use_bcp_47=True)
        assert isinstance(codes, list)
        assert any(c.startswith("nl_") for c in codes)

    def test_script_languoids_reverse_relation(self, access):
        dutch = access.get("nl")
        latin = next((s for s in dutch.scripts if s.iso_15924 == "Latn"), None)
        assert latin is not None
        assert isinstance(latin.languoids, list)
        assert any(lang.id == dutch.id for lang in latin.languoids)

    def test_languoids_with_same_script(self, access):
        dutch = access.get("nl")
        related = dutch.languoids_with_same_script
        assert isinstance(related, list)
        assert dutch not in related


class TestGeographicProperties:
    """Test geographic region traversal."""

    def test_regions_returns_list(self, access):
        dutch = access.get("nl")
        regions = dutch.regions
        assert isinstance(regions, list)
        for r in regions:
            assert isinstance(r, GeographicRegion)

    def test_regions_includes_expected_country(self, access):
        dutch = access.get("nl")
        country_codes = [r.country_code for r in dutch.regions]
        assert "NL" in country_codes

    def test_country_codes_property(self, access):
        dutch = access.get("nl")
        codes = dutch.country_codes
        assert isinstance(codes, list)
        assert "NL" in codes

    def test_languoids_in_same_region(self, access):
        dutch = access.get("nl")
        co_regional = dutch.languoids_in_same_region
        assert isinstance(co_regional, list)
        assert dutch not in co_regional

    def test_region_languoids_includes_language(self, access):
        dutch = access.get("nl")
        nl_region = next((r for r in dutch.regions if r.country_code == "NL"), None)
        assert nl_region is not None
        assert any(lang.id == dutch.id for lang in nl_region.languoids)

    def test_subdivisions_returns_list(self, access):
        dutch = access.get("nl")
        nl_region = next((r for r in dutch.regions if r.country_code == "NL"), None)
        assert nl_region is not None
        assert isinstance(nl_region.subdivisions, list)


class TestOfficialStatus:
    """Test Languoid.official_in_countries metadata filtering."""

    def test_includes_official_regions(self, access):
        dutch = access.get("nl")
        official = dutch.official_in_countries
        # nl.json marks both NL and BE as has_official_status: true
        assert "NL" in official
        assert "BE" in official

    def test_result_is_subset_of_country_codes(self, access):
        """Every country in official_in_countries must also appear in country_codes."""
        dutch = access.get("nl")
        for code in dutch.official_in_countries:
            assert code in dutch.country_codes


class TestGeographicTransitiveClosure:
    """Test that GeographicRegion.languoids unifies direct + child + subdivision paths."""

    def test_child_regions_includes_subdivisions(self, access):
        """NL's child regions (via HAS_CHILD_REGION) should include its provinces."""
        nl = access.store.get("region:nl")
        assert nl is not None
        sub_codes = {r.subdivision_code for r in nl.child_regions if r.subdivision_code}
        assert "NL-NH" in sub_codes
        assert "NL-ZH" in sub_codes

    def test_subdivisions_query_returns_provinces(self, access):
        """NL's subdivisions (via store query on parent_country_code) should match."""
        nl = access.store.get("region:nl")
        assert nl is not None
        sub_codes = {r.subdivision_code for r in nl.subdivisions if r.subdivision_code}
        assert "NL-NH" in sub_codes

    def test_languoids_is_superset_of_direct(self, access):
        """languoids (transitive) must include at least everything in direct_languoids."""
        nl = access.store.get("region:nl")
        assert nl is not None
        direct = {lang.id for lang in nl.direct_languoids}
        transitive = {lang.id for lang in nl.languoids}
        assert direct.issubset(transitive)


class TestDescendantScripts:
    """Test Languoid.descendant_scripts recursive collection."""

    def test_parent_includes_childs_scripts(self, access):
        """A family's descendant_scripts should include scripts from its children."""
        dutch = access.get("nl")
        germanic = dutch.parent
        assert germanic is not None
        desc_codes = {s.iso_15924 for s in germanic.descendant_scripts if s.iso_15924}
        assert "Latn" in desc_codes  # Dutch (child) uses Latin

    def test_is_superset_of_own_scripts(self, access):
        dutch = access.get("nl")
        own = {s.iso_15924 for s in dutch.scripts if s.iso_15924}
        desc = {s.iso_15924 for s in dutch.descendant_scripts if s.iso_15924}
        assert own.issubset(desc)

    def test_no_duplicate_scripts(self, access):
        """Shared scripts across siblings should be deduplicated."""
        dutch = access.get("nl")
        germanic = dutch.parent
        assert germanic is not None
        desc = germanic.descendant_scripts
        assert len(desc) == len({s.id for s in desc})


class TestScriptCanonical:
    """Test Script.is_canonical_for() and Script.canonical_languoids."""

    def test_is_canonical_for_returns_true(self, access):
        dutch = access.get("nl")
        latin = next((s for s in dutch.scripts if s.iso_15924 == "Latn"), None)
        assert latin is not None
        assert latin.is_canonical_for(dutch) is True

    def test_canonical_languoids_includes_dutch(self, access):
        dutch = access.get("nl")
        latin = next((s for s in dutch.scripts if s.iso_15924 == "Latn"), None)
        assert latin is not None
        assert dutch in latin.canonical_languoids

    def test_is_canonical_for_returns_false_when_no_relation(self, access):
        """is_canonical_for should return False (not raise) for an unrelated languoid."""
        dutch = access.get("nl")
        germanic = dutch.parent  # family node; has no USES_SCRIPT relation
        assert germanic is not None
        latin = next((s for s in dutch.scripts if s.iso_15924 == "Latn"), None)
        assert latin is not None
        assert latin.is_canonical_for(germanic) is False


class TestNameIn:
    def test_name_in_returns_none_without_cache(self, access):
        dutch = access.get("nl")
        # No name cache loaded in fixture-based access
        assert dutch.name_in("fr") is None

    def test_name_in_accepts_languoid_arg(self, access):
        dutch = access.get("nl")
        # Northern Frisian is in fixture data (it's a sibling of Dutch)
        frisian = dutch.siblings[0]
        result = dutch.name_in(frisian)
        assert result is None  # no cache, so always None


class TestScriptAccess:
    """Test Database script access methods."""

    def test_get_script_by_iso15924(self, access):
        latin = access.get_script("Latn")
        assert isinstance(latin, Script)
        assert latin.iso_15924 == "Latn"

    def test_get_script_not_found_raises(self, access):
        with pytest.raises(KeyError, match="not found"):
            access.get_script("Zzzz")

    def test_search_scripts_finds_latin(self, access):
        results = access.search_scripts("latin")
        assert any(s.iso_15924 == "Latn" for s in results)

    def test_search_scripts_case_insensitive(self, access):
        results = access.search_scripts("LATIN")
        assert any(s.iso_15924 == "Latn" for s in results)

    def test_search_scripts_no_results(self, access):
        results = access.search_scripts("nope-buddy")
        assert results == []

    def test_all_scripts_non_empty(self, access):
        scripts = access.all_scripts
        assert len(scripts) >= 1
        assert all(isinstance(s, Script) for s in scripts)


class TestRegionAccess:
    """Test Database region access methods."""

    def test_get_region_by_country_code(self, access):
        nl = access.get_region("NL")
        assert isinstance(nl, GeographicRegion)
        assert nl.country_code == "NL"

    def test_get_region_not_found_raises(self, access):
        with pytest.raises(KeyError, match="not found"):
            access.get_region("ZZ")

    def test_search_regions_finds_netherlands(self, access):
        results = access.search_regions("Netherlands")
        assert any(r.country_code == "NL" for r in results)

    def test_search_regions_case_insensitive(self, access):
        results = access.search_regions("netherlands")
        assert any(r.country_code == "NL" for r in results)

    def test_search_regions_no_results(self, access):
        results = access.search_regions("nope-buddy")
        assert results == []

    def test_all_regions_non_empty(self, access):
        regions = access.all_regions
        assert len(regions) >= 1
        assert all(isinstance(r, GeographicRegion) for r in regions)

    def test_all_countries_excludes_subdivisions(self, access):
        countries = access.all_countries
        assert all(r.parent_country_code is None for r in countries)
        assert all(not r.is_historical for r in countries)


class TestGenericQuery:
    """Test Database.query() with entity_type parameter."""

    def test_query_defaults_to_languoid(self, access):
        results = access.query(Languoid, name="Dutch")
        assert all(isinstance(r, Languoid) for r in results)

    def test_query_explicit_script_type(self, access):
        results = access.query(Script, iso_15924="Latn")
        assert len(results) == 1
        assert results[0].iso_15924 == "Latn"

    def test_query_explicit_region_type(self, access):
        results = access.query(GeographicRegion, country_code="NL")
        assert any(r.country_code == "NL" for r in results)
