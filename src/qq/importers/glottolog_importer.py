import csv
import logging
from pathlib import Path

from qq.data_model import DataSource, IdType, LanguoidLevel, RelationType
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid

logger = logging.getLogger(__name__)


class GlottologImporter(BaseImporter):
    """Import language family data from Glottolog"""

    source = DataSource.GLOTTOLOG

    def import_data(self, data_path: Path) -> None:
        """Import from Glottolog CSV files"""
        languoids_file = data_path / "languages.csv"
        if not languoids_file.exists():
            raise FileNotFoundError(f"Glottolog languoid file not found at {data_path}")

        logger.info(f"Importing from Glottolog: {languoids_file}")

        # First pass: create all languoids
        languoids_data = []
        with open(languoids_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                languoids_data.append(row)
                self._import_languoid_first_pass(row)

        # Second pass: create parent-child relationships
        for row in languoids_data:
            self._import_languoid_second_pass(row)

        # Note: Sibling relationships are computed on-the-fly from parent-child relationships
        # See Languoid.siblings property. Storing them would be potentially quadratic...

        self.log_stats()

    def _import_languoid_first_pass(self, row: dict[str, str]) -> None:
        """First pass: create languoid entities"""
        # Note: CSV columns are capitalized (ID, Name, etc.)
        identifiers = {IdType.GLOTTOCODE: row["ID"]}
        if iso_code := row.get("ISO639P3code"):
            identifiers[IdType.ISO_639_3] = iso_code

        languoid = self.get_or_create_languoid(identifiers)

        languoid.name = row.get("Name") if row.get("Name") else None
        if level := row.get("Level"):
            languoid.level = LanguoidLevel[level.upper()]
        languoid.latitude = self._parse_float(row.get("Latitude"))
        languoid.longitude = self._parse_float(row.get("Longitude"))

    def _import_languoid_second_pass(self, row: dict[str, str]) -> None:
        """Second pass: create parent-child relationships only"""
        if not (parent_glottocode := row.get("Family_ID")):
            return

        glottocode = row["ID"]

        child_id = self.resolver.resolve(IdType.GLOTTOCODE, glottocode)
        parent_id = self.resolver.resolve(IdType.GLOTTOCODE, parent_glottocode)

        if not child_id or not parent_id:
            return

        child = self.entity_set.get(child_id)
        parent = self.entity_set.get(parent_id)

        if child and parent and isinstance(child, Languoid) and isinstance(parent, Languoid):
            self.add_bidirectional_relation(child, RelationType.PARENT_LANGUOID, parent, RelationType.CHILD_LANGUOID)

    def _parse_float(self, value: str | None) -> float | None:
        """Parse float value safely"""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
