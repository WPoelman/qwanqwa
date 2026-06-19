import logging
from pathlib import Path

import click

from qq.access import Database
from qq.constants import LOG_SEP, SOURCES_DIR, SOURCES_DOCS_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@click.group()
@click.pass_context
def cli(ctx):
    """qwanqwa - Language metadata toolkit"""
    pass


def _get_source_updater():
    try:
        from qq.sources.updater import SourceUpdater

        return SourceUpdater(SOURCES_DIR)
    except ImportError as e:
        raise click.ClickException(
            f"This command requires build dependencies. Install them with: pip install qwanqwa[build]\n{e}"
        ) from e


def _get_access() -> "Database":
    """Load Database from the default database."""
    return Database.load()


@cli.command()
@click.option("--force", is_flag=True, help="Force update even if up-to-date")
@click.option("--no-rebuild", is_flag=True, help="Skip database rebuild")
@click.option("--source", type=str, help="Update only specific source")
def update(force, no_rebuild, source):
    """Update data sources and rebuild database"""
    updater = _get_source_updater()

    if source:
        from qq.sources.source_config import SourceConfig

        valid = sorted(SourceConfig.get_providers_as_dict(SOURCES_DIR))
        if source not in valid:
            raise click.ClickException(f"Unknown source '{source}'. Valid sources: {', '.join(valid)}")
        updater.update_source(source, force=force, rebuild=not no_rebuild)
    else:
        updater.update_all(force=force, rebuild=not no_rebuild)


@cli.command()
def status():
    """Show status of all data sources"""
    updater = _get_source_updater()
    source_status = updater.get_status()

    click.echo("Data Source Status:")
    for name, status in source_status.items():
        click.echo(f" {name}:")
        click.echo(f"  Version: {status.version}")
        click.echo(f"  Last updated: {status.last_updated}")
        click.echo(f"  Valid: {'✓' if status.is_valid else '✗'}")
        click.echo(f"  Path: {status.data_path}")


@cli.command()
def verify():
    """Verify all data sources"""
    updater = _get_source_updater()
    updater.verify_all()


@cli.command()
def rebuild():
    """Rebuild database from current sources"""
    updater = _get_source_updater()
    updater.rebuild_database()


@cli.command()
@click.argument("code")
@click.option("--type", "id_type", help="Identifier type (BCP_47, ISO_639_3, GLOTTOCODE, etc.)")
def get(code, id_type):
    """Get language information by code"""
    from qq.data_model import IdType

    access = _get_access()

    try:
        if id_type:
            id_type_upper = id_type.upper()
            found_type = next((t for t in IdType if t.name.upper() == id_type_upper), None)
            if found_type is None:
                click.echo(f"Unknown identifier type: {id_type}")
                click.echo(f"Valid types: {', '.join(t.name for t in IdType)}")
                return
            lang = access.get(code, found_type)
        else:
            lang = access.guess(code)
    except KeyError as e:
        click.echo(str(e))
        return

    click.echo(f"\nLanguage: {lang.name or lang.bcp_47}")
    click.echo(f"BCP-47: {lang.bcp_47}")

    click.echo("\nIdentifiers:")
    if lang.iso_639_3:
        click.echo(f"  ISO 639-3: {lang.iso_639_3}")
    if lang.iso_639_2b:
        click.echo(f"  ISO 639-2B: {lang.iso_639_2b}")
    if lang.glottocode:
        click.echo(f"  Glottocode: {lang.glottocode}")
    if lang.wikidata_id:
        click.echo(f"  Wikidata: {lang.wikidata_id}")

    if lang.endonym:
        click.echo(f"\nEndonym: {lang.endonym}")

    if lang.speaker_count is not None:
        click.echo(f"\nSpeakers: {lang.speaker_count:,}")

    if lang.script_codes:
        click.echo(f"\nScripts: {', '.join(lang.script_codes)}")

    if lang.endangerment_status:
        click.echo(f"\nEndangerment: {lang.endangerment_status.value}")


@cli.command()
@click.argument("query")
def search(query):
    """Search for languages by name or identifier"""
    access = _get_access()
    results = access.search(query, limit=20)

    if results:
        click.echo(f"\nFound {len(results)} result(s):\n")
        for lang in results:
            _id = lang.iso_639_3 or lang.glottocode or lang.bcp_47
            click.echo(f"  {lang.name or lang.bcp_47} ({_id})")
    else:
        click.echo(f"No results found for: {query}")


@cli.command()
def validate():
    """Validate database quality and show statistics"""
    from qq.interface import GeographicRegion, Languoid, Script
    from qq.internal.validation import DataValidator

    access = _get_access()

    languoids = access.store.all_of_type(Languoid)
    scripts = access.store.all_of_type(Script)
    regions = access.store.all_of_type(GeographicRegion)

    click.echo("\nDatabase Statistics:")
    click.echo(LOG_SEP)
    click.echo(f"Total languoids: {len(languoids)}")
    click.echo(f"Total scripts: {len(scripts)}")
    click.echo(f"Total regions: {len(regions)}")

    validator = DataValidator(access.store, access.resolver)
    results = validator.validate_all()

    click.echo("\nData Completeness:")
    for field, percentage in results["data_completeness"].items():
        click.echo(f"  {field}: {percentage:.1f}%")

    if results["orphaned_entities"]:
        click.echo(f"\nWarning: {len(results['orphaned_entities'])} orphaned entities")
    if results["broken_relations"]:
        click.echo(f"Warning: {len(results['broken_relations'])} broken relations")
    if results["duplicate_identifiers"]:
        click.echo("\nDuplicate identifiers:")
        for id_type, dups in results["duplicate_identifiers"].items():
            click.echo(f"  {id_type}: {len(dups)} duplicates")


@cli.command()
@click.option("--output", "-o", type=Path, default=SOURCES_DOCS_PATH, help="Output path for documentation file")
def generate_docs(output):
    """Generate sources documentation"""
    try:
        from qq.sources.docs_generator import write_sources_documentation

        write_sources_documentation(SOURCES_DIR, output)
        click.echo(f"Generated sources documentation at: {output}")
    except ImportError as e:
        raise click.ClickException(
            f"This command requires build dependencies. Install them with: pip install qwanqwa[build]\n{e}"
        ) from e


@cli.command("exporters")
def exporters_cmd():
    """List registered output exporters."""
    from qq.exporters import list_exporters

    for name in list_exporters():
        click.echo(name)


@cli.command("export")
@click.argument("name")
@click.option("--output", "output_path", type=Path, required=True, help="Output file or directory")
def export_cmd(name, output_path):
    """Export the installed canonical database snapshot."""
    from qq.constants import DEFAULT_DB_PATH
    from qq.exporters import export as run_export
    from qq.exporters.loading import load_export_context

    try:
        result = run_export(name, load_export_context(DEFAULT_DB_PATH), output_path)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except ModuleNotFoundError as exc:
        if exc.name == "pycldf":
            raise click.ClickException(
                "The cldf exporter requires optional dependencies. Install: pip install qwanqwa[cldf]"
            ) from exc
        raise
    click.echo(f"Wrote {result}")


@cli.command("export-demo")
@click.option("--output", "output_dir", type=Path, default=None, help="Directory for generated demo data")
def export_demo(output_dir):
    """Export static browser demo data"""
    from qq.constants import DEFAULT_DB_PATH
    from qq.explorer.export import DEFAULT_DATA_DIR
    from qq.exporters import export as run_export
    from qq.exporters.loading import load_export_context

    data_dir = run_export("demo", load_export_context(DEFAULT_DB_PATH), output_dir or DEFAULT_DATA_DIR)
    click.echo(f"Wrote {data_dir}")


@cli.command("publish-demo")
@click.argument("output_dir", type=Path)
@click.option("--skip-export", is_flag=True, help="Reuse current demo data instead of regenerating it first")
@click.option("--yes", "assume_yes", is_flag=True, help="Replace an existing output directory without prompting")
def publish_demo_cmd(output_dir, skip_export, assume_yes):
    """Export and copy the browser demo into a target directory"""
    from qq.explorer.publish import publish_demo

    target_dir = output_dir.expanduser().resolve()
    overwrite = False
    if target_dir.exists():
        if not assume_yes:
            click.confirm(f"Replace existing directory {target_dir}?", abort=True)
        overwrite = True

    target_dir = publish_demo(output_dir, skip_export=skip_export, overwrite=overwrite)
    click.echo(f"Published demo to {target_dir}")


@cli.command("prepare-release")
def prepare_release_cmd():
    """Update sources, rebuild data, and refresh release docs"""
    try:
        from qq.release import prepare_release

        prepare_release()
        click.echo("Prepared release artifacts")
    except ImportError as e:
        raise click.ClickException(
            f"This command requires build and CLDF dependencies. "
            f"Install them with: pip install qwanqwa[build,cldf]\n{e}"
        ) from e


if __name__ == "__main__":
    cli()
