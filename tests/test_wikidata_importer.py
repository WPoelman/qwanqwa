import json
from pathlib import Path

from qq.data_model import IdType
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.wikidata_importer import WikidataIso6395Importer, WikidataScriptMetadataImporter
from qq.interface import Languoid, Script
from qq.internal.entity_resolution import EntityResolver


def binding(code, qid, label, glottocode=None):
    item = {
        "item": {"type": "uri", "value": f"http://www.wikidata.org/entity/{qid}"},
        "iso6395": {"type": "literal", "value": code},
        "itemLabel": {"type": "literal", "value": label, "xml:lang": "en"},
    }
    if glottocode is not None:
        item["glottocode"] = {"type": "literal", "value": glottocode}
    return item


def write_wikidata(path, bindings):
    path.write_text(json.dumps({"results": {"bindings": bindings}}), encoding="utf-8")


def test_links_iso6395_to_existing_glottolog_family(tmp_path):
    resolver = EntityResolver()
    glottolog = GlottologImporter(resolver)
    glottolog.import_data(Path(__file__).parent / "fixtures" / "glottolog")

    data_path = tmp_path / "iso6395.json"
    write_wikidata(data_path, [binding("gem", "Q21200", "Germanic languages", "germ1287")])

    importer = WikidataIso6395Importer(resolver)
    importer.import_data(data_path)

    gem_id = resolver.resolve(IdType.ISO_639_5, "gem")
    germ_id = resolver.resolve(IdType.GLOTTOCODE, "germ1287")
    assert isinstance(germ_id, str)
    assert gem_id == germ_id

    entity = importer.entity_set.get(germ_id)
    assert isinstance(entity, Languoid)

    assert entity.iso_639_5 == "gem"
    assert entity.wikidata_id == "Q21200"


def test_skips_wikidata_iso6395_rows_without_glottocode(tmp_path):
    resolver = EntityResolver()
    glottolog = GlottologImporter(resolver)
    glottolog.import_data(Path(__file__).parent / "fixtures" / "glottolog")

    data_path = tmp_path / "iso6395.json"
    write_wikidata(data_path, [binding("art", "Q33215", "constructed language")])

    importer = WikidataIso6395Importer(resolver)
    importer.import_data(data_path)

    assert resolver.resolve(IdType.ISO_639_5, "art") is None


def test_skips_ambiguous_wikidata_iso6395_glottocode_rows(tmp_path):
    resolver = EntityResolver()
    glottolog = GlottologImporter(resolver)
    glottolog.import_data(Path(__file__).parent / "fixtures" / "glottolog")

    data_path = tmp_path / "iso6395.json"
    write_wikidata(
        data_path,
        [
            binding("alg", "Q33392", "Algonquian", "algo1256"),
            binding("alg", "Q33392", "Algonquian", "algo1257"),
        ],
    )

    importer = WikidataIso6395Importer(resolver)
    importer.import_data(data_path)

    assert resolver.resolve(IdType.ISO_639_5, "alg") is None


def script_binding(code, type_qid=None, type_label=None, family=None, sample=None):
    item = {
        "iso15924": {"type": "literal", "value": code},
        "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q38592"},
    }
    if type_qid is not None:
        item["type"] = {"type": "uri", "value": f"http://www.wikidata.org/entity/{type_qid}"}
        item["typeLabel"] = {"type": "literal", "value": type_label, "xml:lang": "en"}
    if family is not None:
        item["familyLabel"] = {"type": "literal", "value": family, "xml:lang": "en"}
    if sample is not None:
        item["sample"] = {"type": "literal", "value": sample}
    return item


def test_enriches_script_metadata_from_wikidata(tmp_path):
    data_path = tmp_path / "scripts.json"
    write_wikidata(
        data_path,
        [
            script_binding("Deva", "Q9779", "alphabet", "Brahmic scripts", "देवनागरी"),
            script_binding("Deva", "Q335806", "abugida", "Brahmic scripts", "देवनागरी"),
        ],
    )

    importer = WikidataScriptMetadataImporter(EntityResolver())
    importer.import_data(data_path)

    script = importer.entity_set.get("script:deva")
    assert isinstance(script, Script)
    assert script.iso_15924 == "Deva"
    assert script.script_type == "abugida"
    assert script.family == "Brahmic scripts"
    assert script.sample == "देवनागरी"


def test_script_metadata_selects_shortest_sample(tmp_path):
    data_path = tmp_path / "scripts.json"
    write_wikidata(
        data_path,
        [
            script_binding("Hang", "Q1191127", "featural writing system", sample="훈민정음"),
            script_binding("Hang", "Q1191127", "featural writing system", sample="한글"),
        ],
    )

    importer = WikidataScriptMetadataImporter(EntityResolver())
    importer.import_data(data_path)

    script = importer.entity_set.get("script:hang")
    assert isinstance(script, Script)
    assert script.script_type == "featural"
    assert script.sample == "한글"


def test_script_metadata_skips_private_use_codes(tmp_path):
    data_path = tmp_path / "scripts.json"
    write_wikidata(data_path, [script_binding("Qaab", "Q9779", "alphabet")])

    importer = WikidataScriptMetadataImporter(EntityResolver())
    importer.import_data(data_path)

    assert importer.entity_set.get("script:qaab") is None
