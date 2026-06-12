import json
from pathlib import Path

from qq.data_model import IdType
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.wikidata_importer import WikidataIso6395Importer
from qq.interface import Languoid
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
