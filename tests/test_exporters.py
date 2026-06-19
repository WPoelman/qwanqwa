from pathlib import Path

import pytest
from click.testing import CliRunner

from qq.cli import cli
from qq.data_model import DataSource, IdType, NameEntry, RelationType
from qq.exporters import ExportContext
from qq.exporters.registry import get_exporter, register_exporter
from qq.importers.base_importer import EntitySet
from qq.interface import Languoid, Script
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge_provenance import MergeSource, merge
from qq.internal.storage import DataManager


class ExampleExporter:
    name = "test-example"

    def export(self, context, output_path):
        return Path(output_path)


def test_exporter_registration_and_duplicate_names():
    exporter = ExampleExporter()
    register_exporter(exporter)
    assert get_exporter(exporter.name) is exporter
    with pytest.raises(ValueError, match="already registered"):
        register_exporter(ExampleExporter())


def test_unknown_exporter_reports_available_names():
    with pytest.raises(KeyError, match="Unknown exporter"):
        get_exporter("does-not-exist")


def test_cli_lists_builtin_exporters():
    result = CliRunner().invoke(cli, ["exporters"])
    assert result.exit_code == 0
    assert result.output.splitlines()[:3] == ["cldf", "demo", "native"]


def test_merge_records_fields_relations_and_duplicate_contributors():
    resolver = EntityResolver()
    lang_id = resolver.find_or_create_canonical_id({IdType.ISO_639_3: "nld"})

    first = EntitySet()
    first_lang = Languoid(lang_id, first, name="Dutch", speaker_count=10)
    first_script = Script("script:latn", first, name="Latin", iso_15924="Latn")
    first.add(first_lang)
    first.add(first_script)
    first_lang.add_relation(RelationType.USES_SCRIPT, first_script.id, is_canonical=True)

    second = EntitySet()
    second_lang = Languoid(lang_id, second, name="Nederlands", speaker_count=20)
    second_script = Script("script:latn", second, name="Latin", iso_15924="Latn")
    second.add(second_lang)
    second.add(second_script)
    second_lang.add_relation(RelationType.USES_SCRIPT, second_script.id)

    store = merge(
        [
            MergeSource("primary", 0, DataSource.GLOTTOLOG, first),
            MergeSource("secondary", 1, DataSource.WIKIPEDIA, second),
        ]
    )

    speaker_records = [
        record
        for record in store.provenance
        if record.kind == "field" and record.entity_id == lang_id and record.field_name == "speaker_count"
    ]
    assert [(record.source_name, record.role) for record in speaker_records] == [
        ("primary", "selected"),
        ("secondary", "candidate"),
    ]
    relation_records = [record for record in store.provenance if record.kind == "relation"]
    assert {record.role for record in relation_records} == {"selected", "contributor"}


def test_native_roundtrip_preserves_context_and_names(tmp_path):
    store = DataStore()
    resolver = EntityResolver()
    lang_id = resolver.find_or_create_canonical_id({IdType.BCP_47: "nl"})
    store.add(Languoid(lang_id, store, name="Dutch", bcp_47="nl"))
    context = ExportContext(
        store,
        resolver,
        names={lang_id: [NameEntry("Dutch", "en", source_name="source-a")]},
        source_metadata={"source-a": {"name": "source-a", "license": "CC0"}},
        build_metadata={"format_version": 2},
    ).attach()
    path = tmp_path / "db.json.gz"

    DataManager("json.gz").save_dataset(store, path, resolver, context.names)
    DataManager("json.gz").load_dataset(path)
    from qq.exporters.loading import load_export_context

    loaded = load_export_context(path)

    assert loaded is not None
    assert loaded.source_metadata["source-a"]["license"] == "CC0"
    assert loaded.names[lang_id][0].source_name == "source-a"
