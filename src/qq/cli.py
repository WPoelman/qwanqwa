import logging
from pathlib import Path

import click

from qq.constants import SOURCES_DIR, SOURCES_DOCS_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@click.group()
@click.pass_context
def cli(ctx):
    """qwanqwa - Language metadata toolkit"""
    pass


def _get_source_updater():
    try:
        from qq.sources.updater import SourceUpdater

        return SourceUpdater(Path.cwd())
    except ImportError as e:
        raise click.ClickException(
            f"This command requires build dependencies. Install them with: pip install qwanqwa[build]\n{e}"
        ) from e


@cli.command()
@click.option("--force", is_flag=True, help="Force update even if up-to-date")
@click.option("--no-rebuild", is_flag=True, help="Skip database rebuild")
@click.option("--source", help="Update only specific source")  # TODO: add options from SourceConfig?
def update(force, no_rebuild, source):
    """Update data sources and rebuild database"""
    updater = _get_source_updater()

    if source:
        updater.update_source(source, force=force, rebuild=not no_rebuild)
    else:
        updater.update_all(force=force, rebuild=not no_rebuild)


@cli.command()
def status():
    """Show status of all data sources"""
    updater = _get_source_updater()
    source_status = updater.get_status()

    click.echo("\nData Source Status:")
    for name, status in source_status.items():
        click.echo(f"\n{name}:")
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
@click.option("--output", "-o", type=Path, default=SOURCES_DOCS_PATH, help="Output path for documentation file")
@click.option("--sources_dir", "-s", type=Path, default=SOURCES_DIR, help="Sources path to generate docs for")
def generate_docs(output, sources_dir):
    """Generate sources documentation"""
    try:
        from qq.sources.docs_generator import write_sources_documentation

        write_sources_documentation(sources_dir, output)
        click.echo(f"Generated sources documentation at: {output}")
    except ImportError as e:
        raise click.ClickException(
            f"This command requires build dependencies. Install them with: pip install qwanqwa[build]\n{e}"
        ) from e


if __name__ == "__main__":
    cli()
