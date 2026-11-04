from qq import Database
from qq.data_model import ExternalResource, ExternalResourceGroup, RelationType
from qq.explorer.export import export_languoid_detail, export_region_detail
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver


def relation_items(detail, label):
    for group in detail["r"]:
        if group["l"] == label:
            return group["i"]
    return []


def test_languoid_demo_export_includes_resource_availability():
    store = DataStore()
    resolver = EntityResolver()
    languoid = Languoid(
        "lang:nld",
        store,
        name="Dutch",
        joshi_rating=4,
        external_resources=[
            ExternalResource(
                label="Hugging Face",
                group=ExternalResourceGroup.DATASETS,
                url="https://huggingface.co/datasets?filter=language:nl",
                count=53,
            ),
            ExternalResource(
                label="Hugging Face",
                group=ExternalResourceGroup.DATASETS,
                url="https://huggingface.co/datasets?filter=language:nld",
                count=17,
            ),
        ],
    )
    store.add(languoid)
    detail = export_languoid_detail(Database(store, resolver), languoid, {}, {})

    assert detail["p"]["joshi_rating"] == "4"
    assert detail["p"]["huggingface_dataset_count"] == "53"


def test_region_demo_export_includes_languoids_and_scripts():
    store = DataStore()
    country = GeographicRegion("region:nl", store, name="Netherlands", country_code="NL")
    languoid = Languoid("lang:nld", store, name="Dutch", bcp_47="nl", iso_639_3="nld")
    script = Script("script:latn", store, name="Latin", iso_15924="Latn")

    for entity in [country, languoid, script]:
        store.add(entity)

    country.add_relation(RelationType.LANGUOIDS_IN_REGION, languoid.id)
    languoid.add_relation(RelationType.SPOKEN_IN_REGION, country.id)
    languoid.add_relation(RelationType.USES_SCRIPT, script.id)

    detail = export_region_detail(country)

    assert "lang:nld" in relation_items(detail, "Languoids")
    assert "script:latn" in relation_items(detail, "Scripts")


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
