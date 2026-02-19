"""
Release preparation script.

Updates documentation with current database statistics:
- Regenerates docs/example.md
- Updates the languoid count in README.md
- Regenerates docs/sources.md
"""

import logging
import re

import qq.constants as const
from qq import Database
from qq.constants import EXAMPLE_PATH, README_PATH, SOURCES_DOCS_PATH
from qq.sources.docs_generator import write_sources_documentation
from qq.sources.updater import SourceUpdater

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def format_languoid_structure(languoid):
    """Generate documentation for a languoid showing all available data."""
    lines = []

    def add(text=""):
        lines.append(text)

    def fmt(value):
        if value is None:
            return "None"
        elif isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, list):
            if not value:
                return "[]"
            elif len(value) <= 3:
                return f"[{', '.join(repr(v) for v in value)}]"
            else:
                return f"[{len(value)} items]"
        else:
            return str(value)

    add(f"# Languoid: {languoid.name} ({languoid.iso_639_3})")
    add()

    add("## Core Identifiers")
    add(f"- **BCP-47**: {fmt(languoid.bcp_47)}")
    add(f"- **ISO 639-3**: {fmt(languoid.iso_639_3)}")
    add(f"- **ISO 639-2B**: {fmt(languoid.iso_639_2b)}")
    add(f"- **Glottocode**: {fmt(languoid.glottocode)}")
    add(f"- **Wikidata ID**: {fmt(languoid.wikidata_id)}")
    add()

    add("## Names")
    add(f"- **Name**: {fmt(languoid.name)}")
    add(f"- **Endonym**: {fmt(languoid.endonym)}")
    add()

    if languoid.speaker_count:
        add("## Population / Speakers")
        add(f"- **Speaker Count**: {languoid.speaker_count:,}")
        add()

    add("## Classification")
    add(f"- **Level**: {fmt(languoid.level)}")
    add(f"- **Scope**: {fmt(languoid.scope)}")
    add(f"- **Type**: {fmt(languoid.status)}")
    add(f"- **Is Macrolanguage**: {fmt(languoid.is_macrolanguage)}")
    add()

    if languoid.endangerment_status:
        add("## Endangerment")
        add(f"- **Status**: {languoid.endangerment_status.value}")
        add()

    if languoid.script_codes:
        add("## Writing Systems")
        add(f"- **Scripts**: {fmt(languoid.script_codes)}")
        add()

    nllb = languoid.nllb_codes()
    if nllb:
        add("## NLLB Translation Codes")
        add(f"- **ISO 639-3 style**: {fmt(list(dict.fromkeys(nllb)))}")
        bcp_nllb = list(dict.fromkeys(languoid.nllb_codes(use_bcp_47=True)))
        if bcp_nllb:
            add(f"- **BCP-47 style**: {fmt(bcp_nllb)}")
        add()

    add("## Relationships (Graph Traversal)")
    add()

    if languoid.parent:
        add("### Parent")
        add(f"- {languoid.parent.name} (`{languoid.parent.iso_639_3 or languoid.parent.glottocode}`)")
        add()

    if languoid.family_tree:
        add("### Language Family Tree")
        add("```")
        for i, ancestor in enumerate(reversed(languoid.family_tree)):
            indent = "  " * i
            level_str = f"[{ancestor.level.value}]" if ancestor.level else ""
            add(f"{indent}{ancestor.name} {level_str}")
        indent = "  " * len(languoid.family_tree)
        level_str = f"[{languoid.level.value}]" if languoid.level else ""
        add(f"{indent}{languoid.name} {level_str}")
        add("```")
        add()

    if languoid.children:
        add(f"### Children ({len(languoid.children)})")
        for child in languoid.children[:5]:
            add(f"- {child.name} (`{child.iso_639_3 or child.glottocode}`)")
        if len(languoid.children) > 5:
            add(f"- ... and {len(languoid.children) - 5} more")
        add()

    canonical = languoid.canonical_scripts
    if canonical:
        add(f"### Scripts ({len(languoid.scripts)})")
        for script in canonical[:5]:
            add(f"- {script.name} (`{script.iso_15924}`)")
        add()

    if languoid.regions:
        add(f"### Geographic Regions ({len(languoid.regions)})")
        for region in languoid.regions[:5]:
            add(f"- {region.name} (`{region.country_code or 'N/A'}`)")
        if len(languoid.regions) > 5:
            add(f"- ... and {len(languoid.regions) - 5} more")
        add()

    descendants = languoid.descendants()
    if descendants:
        add("### Descendants")
        add(f"- **Total**: {len(descendants)} languoids")
        add()

    return "\n".join(lines)


def main():

    # This updates the sources, rebuilds the database, and updates the sources file
    sources_dir = const.SOURCES_DIR
    updater = SourceUpdater(sources_dir)
    updater.update_all(rebuild=True)

    write_sources_documentation(sources_dir, SOURCES_DOCS_PATH)
    logger.info("Updated sources file with last checked info.")

    # Load database and regenerate example docs
    logger.info("Loading database...")
    ld = Database.load()
    languoid_count = len(ld.all_languoids)
    logger.info(f"Loaded {languoid_count:,} languoids")

    am = ld.get("am")
    structure_doc = format_languoid_structure(am)

    EXAMPLE_PATH.write_text(f"# Example\n\n{structure_doc}")
    logger.info(f"Updated {EXAMPLE_PATH}")

    # Update languoid count in README (marker: "~NN,NNN languoids")
    readme_text = README_PATH.read_text()
    new_text = re.sub(r"~[\d,]+ languoids", f"~{languoid_count:,} languoids", readme_text)
    README_PATH.write_text(new_text)
    logger.info(f"Updated languoid count in {README_PATH}")


if __name__ == "__main__":
    main()
