import logging
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

from qq.data_model import DataSource, IdType, RelationType
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


def _split_script_codes(item: str | None) -> list[str] | None:
    if isinstance(item, str):
        if item_s := item.strip():
            return item_s.split(", ")
    return None


class _GlotScriptEntry(BaseModel):
    iso639_3: str  # iso 639 3 code
    iso15924_main: Annotated[list[str] | None, BeforeValidator(_split_script_codes)] = None
    wiki_aux: str | None = None  # conflicting information, only wiki agrees
    sil_aux: str | None = None  # conflicting information, only sil agrees
    lrec2800_aux: str | None = None  # conflicting information, only lrec 2008 agrees
    sil2_aux: str | None = None  # conflicting information between language tag and script source


class GlotscriptImporter(BaseImporter):
    """
    Import script information from Glotscript.
    Glotscript provides detailed script usage information per language.
    """

    source = DataSource.GLOTSCRIPT

    def import_data(self, data_path: Path) -> None:
        """Import from Glotscript CSV."""

        import pandas as pd
        from tqdm import tqdm

        # Try multiple possible filenames
        glotscript_file = data_path / "GlotScript.tsv"
        if not glotscript_file.exists():
            glotscript_file = data_path / "codes.tsv"
        if not glotscript_file.exists():
            raise FileNotFoundError(f"Glotscript file not found in {data_path}")

        records = (
            pd.read_csv(glotscript_file, sep="\t")
            .rename(columns=lambda col: col.replace("-", "_").lower())
            .dropna(subset=["iso639_3"])  # not sure why this is in there
            .replace({pd.NA: None})
            .to_dict("records")
        )

        for row in tqdm(records, desc="Glotscript import"):
            self._import_script_usage(_GlotScriptEntry(**row))

        self.log_stats()

    def _import_script_usage(self, row: _GlotScriptEntry) -> None:
        """Import script usage for a language"""
        # Find languoid by iso_639_3 via resolver
        languoid = self.resolve_languoid(IdType.ISO_639_3, row.iso639_3)
        if not languoid:
            logger.debug(f"Languoid not found for iso_639_3: {row.iso639_3}")
            return

        # iso15924_main is a list of script codes (or None)
        if not row.iso15924_main:
            return

        # Import each script
        for script_code in row.iso15924_main:
            script_id = f"script:{script_code.lower()}"
            script = self.get_or_create_script(script_id)
            script.iso_15924 = script_code

            self.add_bidirectional_relation(languoid, RelationType.USES_SCRIPT, script, RelationType.USED_BY_LANGUOID)
