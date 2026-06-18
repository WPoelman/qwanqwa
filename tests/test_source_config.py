from qq.sources.source_config import SourceConfig


def test_importer_paths_are_resolved_from_configured_sources_dir(tmp_path):
    sources_dir = tmp_path / "sources"
    importers = SourceConfig(sources_dir).get_importers()
    paths = {config.source_name: config.resolve_data_path(sources_dir) for config in importers}

    assert paths["linguameta"] == sources_dir / "linguameta"
    assert paths["wikidata_iso6395"] == sources_dir / "wikidata_iso6395/iso6395.json"
    assert paths["external_resources"] == sources_dir
