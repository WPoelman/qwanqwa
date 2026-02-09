from pathlib import Path

from qq.importers.base_importer import BaseImporter
from qq.importers.glotscript_importer import GlotscriptImporter
from qq.importers.glottolog_importer import GlottologImporter
from qq.sources.providers import (
    APISourceProvider,
    FileDownloadSourceProvider,
    GitSourceProvider,
    SourceProvider,
)


class SourceConfig:
    """
    Sources are the 'raw' data that gets parsed into the qq graph database
    by an Importer.

    This config is used to import the sources in a consistent way.
    """

    @staticmethod
    def get_providers_as_dict(sources_dir: Path) -> dict[str, SourceProvider]:
        """Get dict with name: Provider mapping."""
        return {s.name: s for s in SourceConfig.get_providers(sources_dir)}

    @staticmethod
    def get_providers(sources_dir: Path) -> list[SourceProvider]:
        """
        Get all configured source providers.

        To add a new source:
        1. Add it to this list
        2. Specify the provider type (Git, API, or Directory)
        3. The importer will be automatically used during rebuild
           Do make sure to add an "Importer" to actually extract info from
           the source during a rebuild.
        """
        return [
            GitSourceProvider(
                name="linguameta",
                sources_dir=sources_dir,
                source_url="https://github.com/google-research/url-nlp.git",
                branch="main",
                subpath="linguameta",
                license="CC BY-SA 4.0",
                paper_url="https://aclanthology.org/2024.lrec-main.921/",
                website_url="https://github.com/google-research/url-nlp/tree/main/linguameta",
                notes=(
                    "Individual sources documented in "
                    "[LinguaMeta README](https://github.com/google-research/url-nlp/blob/main/linguameta/README.md)"
                ),
            ),
            GitSourceProvider(
                name="glottolog",
                sources_dir=sources_dir,
                source_url="https://github.com/glottolog/glottolog-cldf.git",
                branch="master",
                subpath="cldf",
                license="CC BY 4.0",
                website_url="https://glottolog.org/",
            ),
            GitSourceProvider(
                name="glotscript",
                sources_dir=sources_dir,
                source_url="https://github.com/cisnlp/glotscript",
                branch="main",
                subpath="metadata",
                license="CC BY-SA 4.0",
                paper_url="https://aclanthology.org/2024.lrec-main.687/",
                website_url="https://github.com/cisnlp/glotscript",
                notes=(
                    "Individual sources documented in "
                    "[GlotScript README](https://github.com/cisnlp/GlotScript/blob/main/metadata/README.md)"
                ),
            ),
            GitSourceProvider(
                name="pycountry",
                sources_dir=sources_dir,
                source_url="https://github.com/pycountry/pycountry",
                branch="main",
                subpath="src/pycountry/databases",
                license="LGPL-2.1",
                notes="Data from [Debian iso-codes](https://salsa.debian.org/iso-codes-team/iso-codes)",
            ),
            APISourceProvider(
                name="wikipedia",
                sources_dir=sources_dir,
                source_url="https://en.wikipedia.org/w/api.php?action=sitematrix&format=json&formatversion=2",
                cache_duration_hours=24 * 7,  # Cache for 1 week
                license="CC BY-SA 4.0",
                website_url="https://meta.wikimedia.org/wiki/List_of_Wikipedias",
            ),
            FileDownloadSourceProvider(
                name="sil",
                sources_dir=sources_dir,
                source_url="https://iso639-3.sil.org/sites/iso639-3/files/downloads/iso-639-3_Retirements.tab",
                filename="iso_639_3_retirements.tab",
                cache_duration_hours=24 * 30,  # Cache for one month
                license="Custom (free use)",
                website_url="https://iso639-3.sil.org/code_tables/download_tables",
                notes="ISO 639-3 retired code mappings maintained by SIL International",
            ),
        ]

    @staticmethod
    def get_importers() -> dict[str, type[BaseImporter]]:
        """
        Each name of a SourceProvider is associated with one or more Importers.
        These importers extract information from the source.
        Currently it's 1-1, but this could change in the future.
        """
        # TODO: finish and make nicer? based on enum instead?
        return {
            # "linguameta": [],
            "glottolog": GlottologImporter,
            "glotscript": GlotscriptImporter,
            # "pycountry": [],
            # "wikipedia": [],
            # "sil": [],
        }
