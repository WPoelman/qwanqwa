from pathlib import Path

from qq.sources.providers import SourceProvider
from qq.sources.source_config import SourceConfig


def _generate_source_section(provider: SourceProvider) -> list[str]:
    """Generate markdown section for a single source."""
    lines = [f"## {provider.name.title() if len(provider.name) > 4 else provider.name.upper()}", ""]

    meta = provider.metadata

    if source_url := meta.source_url:
        lines.append(f"* Source: {source_url}")

    if license := meta.license:
        lines.append(f"* License: {license}")

    if paper := meta.paper_url:
        lines.append(f"* Paper: {paper}")

    if website := meta.website_url:
        if website != source_url:
            lines.append(f"* Website: {website}")

    if updated := meta._last_updated:
        date_str = updated.strftime("%d-%m-%Y")
        lines.append(f"* Last updated: {date_str}")

    if notes := meta.notes:
        lines.append("")
        lines.append(notes)

    lines.append("")
    return lines


def generate_sources_markdown(providers: list[SourceProvider]) -> str:
    """
    Generate markdown documentation for data sources.

    Args:
        providers: list of source providers with their configurations

    Returns:
        Markdown formatted string documenting all sources
    """
    lines = [
        "# Sources",
        "`qq` collects the hard work of many people.",
        " A sincere thank you to all sources listed below for publicly sharing their data!",
        " Copies of the licenses can be found in [./licenses].",
        "",
    ]

    # Sort providers by name for consistency
    for provider in sorted(providers, key=lambda s: s.name):
        lines.extend(_generate_source_section(provider))

    return "\n".join(lines)


def write_sources_documentation(sources_dir: Path, output_path: Path) -> None:
    """
    Generate and write sources documentation to a file.

    Args:
        output_path: Path where the markdown file should be written
    """
    content = generate_sources_markdown(SourceConfig.get_providers(sources_dir))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
