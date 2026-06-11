import json

from qq.data_model import DataSource, IdType
from qq.importers.base_importer import EntitySet
from qq.importers.external_resource_importer import ExternalResourceImporter
from qq.interface import Languoid
from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge import merge
from qq.sources.source_config import SourceConfig


def test_applies_source_backed_resource_links(tmp_path):
    sources_dir = tmp_path / "sources"
    grambank_dir = sources_dir / "grambank"
    grambank_dir.mkdir(parents=True)
    (grambank_dir / "languages.csv").write_text(
        "ID,Name,Glottocode\ndutc1256,Dutch,dutc1256\nmissing1234,Missing,missing1234\n",
        encoding="utf-8",
    )
    afbo_dir = sources_dir / "afbo"
    afbo_dir.mkdir(parents=True)
    (afbo_dir / "languages.csv").write_text(
        "ID,Name,Glottocode\ndutchnld,Dutch,dutc1256\n",
        encoding="utf-8",
    )

    resolver = EntityResolver()
    canonical_id = resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "dutc1256"})
    base_entities = EntitySet()
    base_entities.add(Languoid(canonical_id, base_entities, name="Dutch", glottocode="dutc1256"))

    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)
    store = merge([(DataSource.GLOTTOLOG, base_entities), (DataSource.EXTERNAL_RESOURCES, importer.entity_set)])

    lang = store.get(canonical_id)
    assert isinstance(lang, Languoid)

    resource_by_label = {resource.label: resource for resource in lang.external_resources}

    assert resource_by_label["Glottolog"].url == "https://glottolog.org/resource/languoid/id/dutc1256"
    assert resource_by_label["Grambank"].url == "https://grambank.clld.org/languages/dutc1256"
    assert resource_by_label["AfBo"].url == "https://afbo.info/languages/dutchnld"
    assert "PHOIBLE" not in resource_by_label
    assert "WALS" not in resource_by_label


def test_deduplicates_resource_links(tmp_path):
    sources_dir = tmp_path / "sources"
    grambank_dir = sources_dir / "grambank"
    grambank_dir.mkdir(parents=True)
    (grambank_dir / "languages.csv").write_text(
        "ID,Name,Glottocode\ndutc1256,Dutch,dutc1256\n",
        encoding="utf-8",
    )

    resolver = EntityResolver()
    canonical_id = resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "dutc1256"})
    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)
    importer.import_data(sources_dir)

    lang = importer.entity_set.get(canonical_id)
    keys = [(resource.label, resource.code) for resource in lang.external_resources]

    assert keys.count(("Glottolog", "dutc1256")) == 1
    assert keys.count(("Grambank", "dutc1256")) == 1


def test_applies_dspace_item_json_resource_links(tmp_path):
    sources_dir = tmp_path / "sources"
    ud_dir = sources_dir / "universal_dependencies"
    ud_dir.mkdir(parents=True)
    (ud_dir / "item.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "dc.language.iso": [
                        {"value": "nld"},
                        {"value": "eng"},
                        {"value": "missing"},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    resolver = EntityResolver()
    canonical_id = resolver.find_or_create_canonical_id({IdType.ISO_639_3: "nld"})

    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)

    lang = importer.entity_set.get(canonical_id)
    resource_by_label = {resource.label: resource for resource in lang.external_resources}

    assert resource_by_label["Universal Dependencies"].code == "nld"
    assert resource_by_label["Universal Dependencies"].url == "http://hdl.handle.net/11234/1-6149"


def test_applies_huggingface_tag_resource_links(tmp_path):
    sources_dir = tmp_path / "sources"
    hf_dir = sources_dir / "huggingface_dataset_tags"
    hf_dir.mkdir(parents=True)
    (hf_dir / "tags.json").write_text(
        json.dumps(
            {
                "language": [
                    {"id": "language:nl", "dataset_count": 53},
                    {"id": "language:nld", "dataset_count": 17},
                    {"id": "language:dut", "dataset_count": 4},
                    {"id": "license:cc-by-4.0", "dataset_count": 100},
                ]
            }
        ),
        encoding="utf-8",
    )

    resolver = EntityResolver()
    canonical_id = resolver.find_or_create_canonical_id(
        {IdType.BCP_47: "nl", IdType.ISO_639_1: "nl", IdType.ISO_639_3: "nld"}
    )

    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)

    lang = importer.entity_set.get(canonical_id)
    hf_resources = [resource for resource in lang.external_resources if resource.label == "Hugging Face"]

    assert {(resource.code, resource.count) for resource in hf_resources} == {("nl", 53), ("nld", 17)}
    assert {resource.url for resource in hf_resources} == {
        "https://huggingface.co/datasets?filter=language:nl",
        "https://huggingface.co/datasets?filter=language:nld",
    }


def test_can_keep_one_source_resource_per_languoid(tmp_path):
    sources_dir = tmp_path / "sources"
    wals_dir = sources_dir / "wals"
    wals_dir.mkdir(parents=True)
    (wals_dir / "languages.csv").write_text(
        "ID,Name,Glottocode\nger,German,stan1295\ngbl,German dialect,stan1295\n",
        encoding="utf-8",
    )

    resolver = EntityResolver()
    canonical_id = resolver.find_or_create_canonical_id({IdType.GLOTTOCODE: "stan1295"})

    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)

    lang = importer.entity_set.get(canonical_id)
    wals_resources = [resource for resource in lang.external_resources if resource.label == "WALS"]

    assert [(resource.code, resource.url) for resource in wals_resources] == [
        ("ger", "https://wals.info/languoid/lect/wals_code_ger")
    ]
