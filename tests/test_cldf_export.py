import csv

import pytest

from qq.data_model import (
    ExternalResource,
    ExternalResourceGroup,
    IdType,
    NameEntry,
    RelationType,
)
from qq.exporters.cldf import CLDFExporter
from qq.exporters.context import ExportContext, ProvenanceRecord
from qq.interface import GeographicRegion, Languoid, Script
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver

pycldf = pytest.importorskip("pycldf")


def fixture_context():
    store = DataStore()
    resolver = EntityResolver()
    lang_id = resolver.find_or_create_canonical_id(
        {IdType.BCP_47: "nl", IdType.ISO_639_3: "nld", IdType.GLOTTOCODE: "dutc1256"}
    )
    locale_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "en", IdType.ISO_639_3: "eng"})
    resolver.register_deprecated(IdType.ISO_639_3, "dut", "change")

    language = Languoid(
        lang_id,
        store,
        name="Dutch",
        bcp_47="nl",
        iso_639_3="nld",
        glottocode="dutc1256",
        latitude=52.0,
        longitude=5.0,
        external_resources=[
            ExternalResource(
                "Example",
                ExternalResourceGroup.DATASETS,
                "https://example.test/nld",
                source_name="example",
            )
        ],
    )
    locale = Languoid(locale_id, store, name="English", bcp_47="en", iso_639_3="eng")
    script = Script("script:latn", store, name="Latin", iso_15924="Latn")
    region = GeographicRegion("region:nl", store, name="Netherlands", country_code="NL")
    for entity in (language, locale, script, region):
        store.add(entity)
    language.add_relation(RelationType.USES_SCRIPT, script.id, is_canonical=True)
    language.add_relation(RelationType.SPOKEN_IN_REGION, region.id)

    return ExportContext(
        store,
        resolver,
        names={lang_id: [NameEntry("Dutch", "en", locale_id=locale_id, is_canonical=True, source_name="example")]},
        source_metadata={
            "example": {
                "name": "example",
                "source_url": "https://example.test",
                "license": "CC0",
            }
        },
        provenance=[
            ProvenanceRecord(
                kind="field",
                entity_id=lang_id,
                field_name="name",
                source_name="example",
                role="selected",
                strategy="single_source",
                value="Dutch",
                priority=0,
            )
        ],
        qq_version="test",
    ).attach()


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_cldf_export_validates_and_has_stable_safe_ids(tmp_path):
    target = tmp_path / "cldf"
    CLDFExporter().export(fixture_context(), target)

    dataset = pycldf.Dataset.from_metadata(target / "cldf-metadata.json")
    assert dataset.validate(log=None)
    assert read_rows(target / "languages.csv")[0]["ID"].startswith("lang_")
    assert ":" not in read_rows(target / "languages.csv")[0]["ID"]
    assert read_rows(target / "relations.csv")[0]["Source_Language_ID"]
    assert read_rows(target / "provenance.csv")[0]["Source_ID"] == "example"
    assert (target / "README.md").exists()
    assert (target / "LICENSE").exists()
    assert (target / "SHA256SUMS").exists()


def test_cldf_export_is_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    context = fixture_context()
    CLDFExporter().export(context, first)
    CLDFExporter().export(context, second)

    assert {path.name: path.read_bytes() for path in first.iterdir() if path.is_file()} == {
        path.name: path.read_bytes() for path in second.iterdir() if path.is_file()
    }
