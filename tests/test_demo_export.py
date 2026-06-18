from qq.data_model import RelationType
from qq.explorer.export import export_region_detail
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.data_store import DataStore


def relation_items(detail, label):
    for group in detail["r"]:
        if group["l"] == label:
            return group["i"]
    return []


def test_region_demo_export_includes_languoids_and_scripts_from_subregions():
    store = DataStore()
    country = GeographicRegion("region:nl", store, name="Netherlands", country_code="NL")
    subdivision = GeographicRegion(
        "region:nl-nh",
        store,
        name="Noord-Holland",
        subdivision_code="NL-NH",
        parent_country_code="NL",
    )
    languoid = Languoid("lang:nld", store, name="Dutch", bcp_47="nl", iso_639_3="nld")
    script = Script("script:latn", store, name="Latin", iso_15924="Latn")

    for entity in [country, subdivision, languoid, script]:
        store.add(entity)

    country.add_relation(RelationType.HAS_CHILD_REGION, subdivision.id)
    subdivision.add_relation(RelationType.IS_PART_OF, country.id)
    subdivision.add_relation(RelationType.LANGUOIDS_IN_REGION, languoid.id)
    languoid.add_relation(RelationType.SPOKEN_IN_REGION, subdivision.id)
    languoid.add_relation(RelationType.USES_SCRIPT, script.id)

    detail = export_region_detail(country)

    assert "lang:nld" in relation_items(detail, "Languoids")
    assert "script:latn" in relation_items(detail, "Scripts")


def test_region_demo_export_does_not_inherit_parent_languoids_for_subdivision():
    store = DataStore()
    country = GeographicRegion("region:nl", store, name="Netherlands", country_code="NL")
    subdivision = GeographicRegion(
        "region:nl-nh",
        store,
        name="Noord-Holland",
        subdivision_code="NL-NH",
        parent_country_code="NL",
    )
    languoid = Languoid("lang:nld", store, name="Dutch", bcp_47="nl", iso_639_3="nld")

    for entity in [country, subdivision, languoid]:
        store.add(entity)

    country.add_relation(RelationType.HAS_CHILD_REGION, subdivision.id)
    subdivision.add_relation(RelationType.IS_PART_OF, country.id)
    country.add_relation(RelationType.LANGUOIDS_IN_REGION, languoid.id)
    languoid.add_relation(RelationType.SPOKEN_IN_REGION, country.id)

    detail = export_region_detail(subdivision)

    assert "lang:nld" not in relation_items(detail, "Languoids")


def test_script_demo_export_includes_wikidata_metadata():
    from qq.explorer.export import export_script_detail

    store = DataStore()
    script = Script(
        "script:deva",
        store,
        name="Devanagari",
        iso_15924="Deva",
        script_type="abugida",
        family="Brahmic scripts",
        sample="देवनागरी",
    )
    store.add(script)

    detail = export_script_detail(script)

    assert detail["p"]["script_type"] == "abugida"
    assert detail["p"]["family"] == "Brahmic scripts"
    assert detail["p"]["sample"] == "देवनागरी"
