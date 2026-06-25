import logging
from pathlib import Path
from typing import Generator

from qq.data_model import CanonicalId, DataSource, DeprecatedCode, IdType
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid

logger = logging.getLogger(__name__)


class IANAImporter(BaseImporter):
    """Import useful BCP-47 records from the IANA Language Subtag Registry.

    The IANA Language Subtag Registry (BCP 47 / RFC 5646) is the authoritative
    source for BCP-47 language, script, and region subtags, including deprecated
    language subtags such as ``iw`` (Hebrew), ``in`` (Indonesian), ``ji``
    (Yiddish), and ``mo`` (Moldavian).
    """

    source = DataSource.IANA

    def import_data(self, data_path: Path) -> None:
        """Import from the IANA language subtag registry file."""
        registry_file = data_path / "language-subtag-registry"

        records = list(self._parse_registry(registry_file))
        logger.info(f"Parsed {len(records)} IANA registry records")

        dep_count = 0
        resolved_count = 0
        language_count = 0
        script_count = 0
        region_count = 0

        for record in records:
            record_type = record.get("Type")
            if record_type == "language" and self._import_language_record(record):
                language_count += 1
            elif record_type == "script" and self._import_script_record(record):
                script_count += 1
            elif record_type == "region" and self._import_region_record(record):
                region_count += 1

            if record_type != "language" or "Deprecated" not in record:
                continue

            subtag = record.get("Subtag", "").strip()
            if not subtag:
                continue

            preferred = record.get("Preferred-Value", "").strip() or None
            deprecated_date = record.get("Deprecated", "").strip()
            description = record.get("Description", "").strip() or None

            reason = f"Deprecated {deprecated_date}"
            if preferred:
                reason += f", use {preferred!r} instead"

            id_type = IdType.ISO_639_1 if len(subtag) == 2 else IdType.ISO_639_3
            self.resolver.register_deprecated(id_type, subtag, reason)
            dep_count += 1

            if preferred:
                canonical_id = self._resolve_preferred(preferred)
                if canonical_id:
                    self.resolver.register_alias(id_type, subtag, canonical_id)
                    languoid = self._get_or_stub_languoid(canonical_id)
                    if languoid is not None:
                        dc = DeprecatedCode(
                            code=subtag,
                            code_type=id_type,
                            name=description,
                            effective=deprecated_date or None,
                            remedy=f"Use {preferred!r} instead",
                        )
                        if languoid.deprecated_codes is None:
                            languoid.deprecated_codes = []
                        languoid.deprecated_codes.append(dc)
                    resolved_count += 1

        logger.info(
            f"IANA: {dep_count} deprecated language subtags imported, "
            f"{resolved_count} resolved to preferred replacements; "
            f"{language_count} active language aliases, {script_count} scripts, {region_count} regions"
        )
        self.log_stats()

    def _import_language_record(self, record: dict[str, str]) -> bool:
        subtag = record.get("Subtag", "").strip()
        if not subtag:
            return False

        canonical_id = self._resolve_preferred(subtag)
        if canonical_id is None:
            return False

        self.resolver.register_alias(IdType.BCP_47, subtag, canonical_id)
        return True

    def _import_script_record(self, record: dict[str, str]) -> bool:
        subtag = record.get("Subtag", "").strip()
        if not subtag:
            return False

        script = self.get_or_create_script(f"script:{subtag.lower()}")
        script.iso_15924 = subtag
        if description := record.get("Description", "").strip():
            script.name = description
        return True

    def _import_region_record(self, record: dict[str, str]) -> bool:
        subtag = record.get("Subtag", "").strip()
        if not subtag or len(subtag) != 2 or not subtag.isalpha():
            return False

        region = self.get_or_create_region(f"region:{subtag.lower()}")
        region.country_code = subtag
        if description := record.get("Description", "").strip():
            region.name = description
        return True

    def _resolve_preferred(self, preferred: str) -> CanonicalId | None:
        """Try to resolve a Preferred-Value code to a canonical ID."""
        id_types = [IdType.ISO_639_1, IdType.BCP_47] if len(preferred) == 2 else [IdType.ISO_639_3, IdType.BCP_47]
        for id_type in id_types:
            canonical = self.resolver.resolve(id_type, preferred)
            if canonical is not None:
                return canonical
        return None

    def _get_or_stub_languoid(self, canonical_id: CanonicalId) -> Languoid | None:
        """Return existing entity from EntitySet or create a stub for the canonical ID."""
        entity = self.entity_set.get(canonical_id)
        if entity is not None and isinstance(entity, Languoid):
            return entity

        identity = self.resolver.get_identity(canonical_id)
        if identity is None:
            return None

        kwargs = self._identifiers_to_kwargs(identity)
        languoid = Languoid(canonical_id, self.entity_set, **kwargs)
        self.entity_set.add(languoid)
        self.stats.entities_created += 1
        return languoid

    @staticmethod
    def _parse_registry(path: Path) -> Generator[dict[str, str], None, None]:
        """Parse IANA registry format into a sequence of field dicts.

        Records are separated by ``%%`` lines.  Continuation lines (starting
        with a single space) are appended to the previous field value.
        The first record contains only the ``File-Date`` header and is yielded
        like any other (callers filter by ``Type``).
        """
        current: dict[str, str] = {}
        last_key: str | None = None

        with open(path, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.rstrip("\n")

                if line == "%%":
                    if current:
                        yield current
                    current = {}
                    last_key = None
                elif line.startswith(" ") and last_key is not None:
                    current[last_key] = current[last_key] + " " + line.strip()
                elif ": " in line:
                    key, _, value = line.partition(": ")
                    key = key.strip()
                    if key not in current:
                        current[key] = value.strip()
                    last_key = key

        if current:
            yield current
