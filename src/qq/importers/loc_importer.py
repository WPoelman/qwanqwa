import logging
from pathlib import Path

from qq.data_model import CanonicalId, DataSource, IdType, NameEntry
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


class LOCImporter(BaseImporter):
    """Import ISO 639-2 / ISO 639-1 mappings from the Library of Congress."""

    source = DataSource.LOC

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_data: dict[CanonicalId, list[NameEntry]] = {}

    @property
    def name_data(self) -> dict[CanonicalId, list[NameEntry]]:
        return self._name_data

    def import_data(self, data_path: Path) -> None:
        """Import LOC's pipe-separated ISO 639-2 table."""
        table_file = data_path / "ISO-639-2_utf-8.txt" if data_path.is_dir() else data_path
        if not table_file.exists():
            raise FileNotFoundError(f"LOC ISO 639-2 table not found: {table_file}")

        imported = 0
        with open(table_file, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue

                bibliographic, terminological, alpha_2, english_name, *_ = line.split("|")
                iso_639_2b = bibliographic.strip() or None
                iso_639_2t = terminological.strip() or iso_639_2b
                iso_639_1 = alpha_2.strip() or None
                name = self._primary_name(english_name)

                identifiers = {}
                canonical_iso3 = self.resolver.resolve(IdType.ISO_639_3, iso_639_2t) if iso_639_2t else None
                canonical_iso5 = self.resolver.resolve(IdType.ISO_639_5, iso_639_2t) if iso_639_2t else None
                if canonical_iso3 and iso_639_2t:
                    identifiers[IdType.ISO_639_3] = iso_639_2t
                elif canonical_iso5 and iso_639_2t:
                    identifiers[IdType.ISO_639_5] = iso_639_2t
                if iso_639_1:
                    identifiers[IdType.ISO_639_1] = iso_639_1
                if not identifiers and iso_639_2b:
                    identifiers[IdType.ISO_639_2B] = iso_639_2b

                languoid = self.get_or_create_languoid(identifiers)

                if iso_639_2b:
                    languoid.iso_639_2b = iso_639_2b
                    self.resolver.register_alias(IdType.ISO_639_2B, iso_639_2b, languoid.id)
                if canonical_iso3 and iso_639_2t:
                    languoid.iso_639_3 = iso_639_2t
                    self.resolver.register_alias(IdType.ISO_639_2T, iso_639_2t, languoid.id)
                if iso_639_1:
                    languoid.iso_639_1 = iso_639_1
                    self.resolver.register_alias(IdType.ISO_639_1, iso_639_1, languoid.id)
                    if self.resolver.resolve(IdType.BCP_47, iso_639_1) is None:
                        self.resolver.register_alias(IdType.BCP_47, iso_639_1, languoid.id)
                if name and not languoid.name:
                    languoid.name = name
                if name:
                    self._name_data[languoid.id] = [NameEntry(name=name, bcp_47_code="en", is_canonical=True)]

                imported += 1

        logger.info(f"Imported {imported} LOC ISO 639-2 rows")
        self.log_stats()

    @staticmethod
    def _primary_name(name: str) -> str | None:
        clean = name.strip()
        if not clean:
            return None
        return clean.split(";")[0].strip()
