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
    assert resource_by_label["Glottolog"].source_name == "qq"
    assert resource_by_label["Glottolog"].match_id_type is IdType.GLOTTOCODE
    assert resource_by_label["Glottolog"].match_value == "dutc1256"

    assert resource_by_label["Grambank"].url == "https://grambank.clld.org/languages/dutc1256"
    assert resource_by_label["Grambank"].source_name == "grambank"
    assert resource_by_label["Grambank"].source_file == "languages.csv"
    assert resource_by_label["Grambank"].match_column == "Glottocode"
    assert resource_by_label["Grambank"].match_id_type is IdType.GLOTTOCODE
    assert resource_by_label["Grambank"].match_value == "dutc1256"
    assert resource_by_label["Grambank"].code_column == "ID"

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
    assert isinstance(lang, Languoid)

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
    assert isinstance(lang, Languoid)

    resource_by_label = {resource.label: resource for resource in lang.external_resources}

    assert resource_by_label["Universal Dependencies"].code == "nld"
    assert resource_by_label["Universal Dependencies"].url == "http://hdl.handle.net/11234/1-6149"
    assert resource_by_label["Universal Dependencies"].source_name == "universal_dependencies"
    assert resource_by_label["Universal Dependencies"].source_file == "item.json"
    assert resource_by_label["Universal Dependencies"].match_column == "dc.language.iso"
    assert resource_by_label["Universal Dependencies"].match_id_type is IdType.ISO_639_3
    assert resource_by_label["Universal Dependencies"].match_value == "nld"


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
                    {"id": "language:dut", "dataset_count": 0},
                    {"id": "license:cc-by-4.0", "dataset_count": 100},
                ]
            }
        ),
        encoding="utf-8",
    )

    resolver = EntityResolver()
    canonical_id = resolver.find_or_create_canonical_id(
        {IdType.BCP_47: "nl", IdType.ISO_639_1: "nl", IdType.ISO_639_3: "nld", IdType.ISO_639_2B: "dut"}
    )

    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)

    lang = importer.entity_set.get(canonical_id)
    assert isinstance(lang, Languoid)

    hf_resources = [resource for resource in lang.external_resources if resource.label == "Hugging Face"]

    assert {(resource.code, resource.count) for resource in hf_resources} == {("nl", 53), ("nld", 17)}
    assert {(resource.match_value, resource.match_id_type) for resource in hf_resources} == {
        ("nl", IdType.BCP_47),
        ("nld", IdType.ISO_639_3),
    }
    assert {resource.source_name for resource in hf_resources} == {"huggingface_dataset_tags"}
    assert {resource.source_file for resource in hf_resources} == {"tags.json"}
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
    assert isinstance(lang, Languoid)

    wals_resources = [resource for resource in lang.external_resources if resource.label == "WALS"]

    assert [(resource.code, resource.url) for resource in wals_resources] == [
        ("ger", "https://wals.info/languoid/lect/wals_code_ger")
    ]


def test_applies_wikidata_sitelink_resource_links(tmp_path):
    sources_dir = tmp_path / "sources"
    wikidata_dir = sources_dir / "wikidata_enwiki_sitelinks"
    wikidata_dir.mkdir(parents=True)
    (wikidata_dir / "sitelinks.json").write_text(
        json.dumps(
            {
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q188"},
                            "article": {"value": "https://en.wikipedia.org/wiki/German_language"},
                            "articleTitle": {"value": "German language"},
                        },
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q999"},
                            "articleTitle": {"value": "Missing URL"},
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    resolver = EntityResolver()
    german_id = resolver.find_or_create_canonical_id({IdType.WIKIDATA_ID: "Q188"})
    no_enwiki_id = resolver.find_or_create_canonical_id({IdType.WIKIDATA_ID: "Q12952751"})

    importer = ExternalResourceImporter(resolver, SourceConfig.get_external_resource_definitions(sources_dir))
    importer.import_data(sources_dir)

    german = importer.entity_set.get(german_id)
    assert isinstance(german, Languoid)

    resource_by_label = {resource.label: resource for resource in german.external_resources}
    assert resource_by_label["English Wikipedia"].code == "German language"
    assert resource_by_label["English Wikipedia"].url == "https://en.wikipedia.org/wiki/German_language"
    assert resource_by_label["English Wikipedia"].source_name == "wikidata_enwiki_sitelinks"
    assert resource_by_label["English Wikipedia"].source_file == "sitelinks.json"
    assert resource_by_label["English Wikipedia"].match_column == "item"
    assert resource_by_label["English Wikipedia"].match_id_type is IdType.WIKIDATA_ID
    assert resource_by_label["English Wikipedia"].match_value == "Q188"
    assert resource_by_label["English Wikipedia"].code_column == "articleTitle"
    assert resource_by_label["English Wikipedia"].url_column == "article"

    no_enwiki = importer.entity_set.get(no_enwiki_id)
    assert isinstance(no_enwiki, Languoid)
    assert "English Wikipedia" not in {resource.label for resource in no_enwiki.external_resources}
