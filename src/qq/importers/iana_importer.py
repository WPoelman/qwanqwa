import logging
from pathlib import Path
from typing import Generator

from qq.data_model import CanonicalId, DataSource, DeprecatedCode, IdType
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid

logger = logging.getLogger(__name__)


class IANAImporter(BaseImporter):
    """Import deprecated language subtags from the IANA Language Subtag Registry.

    The IANA Language Subtag Registry (BCP 47 / RFC 5646) is the authoritative
    source for deprecated BCP-47 language subtags such as the old ISO 639-1 codes
    ``iw`` (Hebrew), ``in`` (Indonesian), ``ji`` (Yiddish), and ``mo`` (Moldavian).

    For each deprecated ``Type: language`` this importer:
    - registers the deprecated subtag in the resolver's deprecated codes
    - if a ``Preferred-Value`` is given, registers an alias from the old code to
      the canonical entity of the preferred code and attaches a ``DeprecatedCode``
      object to that languoid.
    """

    source = DataSource.IANA

    def import_data(self, data_path: Path) -> None:
        """Import from the IANA language subtag registry file."""
        registry_file = data_path / "language-subtag-registry"

        records = list(self._parse_registry(registry_file))
        logger.info(f"Parsed {len(records)} IANA registry records")

        dep_count = 0
        resolved_count = 0

        for record in records:
            if record.get("Type") != "language":
                continue
            if "Deprecated" not in record:
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

            # TODO: maybe it could also be ISO 639 2B? Is this derivable from the preferred value?
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
            f"{resolved_count} resolved to preferred replacements"
        )
        self.log_stats()

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
                    # Continuation line: append to last field
                    current[last_key] = current[last_key] + " " + line.strip()
                elif ": " in line:
                    key, _, value = line.partition(": ")
                    key = key.strip()
                    # If key already present (e.g. multiple Description lines),
                    # keep the first value (primary description).
                    if key not in current:
                        current[key] = value.strip()
                    last_key = key

        if current:
            yield current
