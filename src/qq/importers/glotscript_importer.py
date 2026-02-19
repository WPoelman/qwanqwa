import logging
import math
from pathlib import Path

import pandas as pd  # TODO: also get rid of pandas dependency?

from qq.data_model import DataSource, IdType, RelationType
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


def _clean_nan_records(records: list[dict]) -> list[dict]:
    """Replace float('nan') values with None (pandas .replace() doesn't catch them)."""
    for rec in records:
        for key, val in rec.items():
            if isinstance(val, float) and math.isnan(val):
                rec[key] = None
    return records


class GlotscriptImporter(BaseImporter):
    """
    Import script information from Glotscript.
    Glotscript provides detailed script usage information per language.
    """

    source = DataSource.GLOTSCRIPT

    def import_data(self, data_path: Path) -> None:
        """Import from Glotscript CSV."""

        # Try multiple possible filenames
        glotscript_file = data_path / "GlotScript.tsv"
        if not glotscript_file.exists():
            glotscript_file = data_path / "codes.tsv"
        if not glotscript_file.exists():
            raise FileNotFoundError(f"Glotscript file not found in {data_path}")

        records = (
            pd.read_csv(glotscript_file, sep="\t")
            .rename(columns=lambda col: col.replace("-", "_").lower())
            .dropna(subset=["iso639_3"])
            .replace({pd.NA: None})
            .to_dict("records")
        )

        # pandas .replace() doesn't catch float('nan'); clean up explicitly
        _clean_nan_records(records)

        for row in records:
            self._import_script_usage(row)

        self.log_stats()

    def _import_script_usage(self, row: dict[str, str | None]) -> None:
        """Import script usage for a language"""
        # Find languoid by iso_639_3 via resolver
        if not (code := row.get("iso639_3")):
            logger.debug(f"No iso code in glotscript row {row}")
            return

        if not (languoid := self.resolve_languoid(IdType.ISO_639_3, code)):
            logger.debug(f"Languoid not found for iso_639_3: {row['iso639_3']}")
            return

        # iso15924_main is a list of script codes (or None)
        if not isinstance(row["iso15924_main"], str):
            return

        if not (codes := row["iso15924_main"].strip().split(", ")):
            return

        for script_code in codes:
            # Skip Braille: it is a tactile transcription system, not a visual script,
            # and adds no linguistic information for NLP purposes.
            if script_code == "Brai":
                continue

            script_id = f"script:{script_code.lower()}"
            script = self.get_or_create_script(script_id)
            script.iso_15924 = script_code

            self.add_bidirectional_relation(languoid, RelationType.USES_SCRIPT, script, RelationType.USED_BY_LANGUOID)
