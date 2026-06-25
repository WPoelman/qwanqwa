import logging
import re
from pathlib import Path

from qq.data_model import (
    CanonicalId,
    DataSource,
    DeprecatedCode,
    DeprecationReason,
    IdType,
    LanguageScope,
    LanguageStatus,
    NameEntry,
)
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


class SILImporter(BaseImporter):
    """Import ISO 639-3 data from SIL.

    Parses the active code table when present and the retirements TSV when present.
    For codes with replacements (reasons C/M/D), registers the old code as an
    alias pointing to the replacement languoid. For all retired codes, registers
    them in the resolver's deprecated code tracking.
    """

    source = DataSource.SIL

    tag_re = re.compile(r"\[([a-z]{3})\]")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_data: dict[CanonicalId, list[NameEntry]] = {}

    @property
    def name_data(self) -> dict[CanonicalId, list[NameEntry]]:
        return self._name_data

    def import_data(self, data_path: Path) -> None:
        """Import from SIL ISO 639-3 TSV files."""
        active_file = self._find_file(data_path, ["iso-639-3.tab", "iso_639_3.tab", "iso-639-3.tsv"])
        retirements_file = self._find_file(
            data_path,
            ["iso-639-3_Retirements.tab", "iso_639_3_retirements.tab", "iso-639-3-retirements.tab"],
        )

        if active_file:
            self._import_active_codes(active_file)
        if retirements_file:
            self._import_retirements(retirements_file)
        if not active_file and not retirements_file:
            raise FileNotFoundError(f"No SIL ISO 639-3 tables found in {data_path}")

        self.log_stats()

    def _import_active_codes(self, active_file: Path) -> None:
        """Import active ISO 639-3 code table."""
        import pandas as pd

        df = pd.read_csv(active_file, sep="\t").rename(columns=lambda col: col.strip())

        logger.info(f"Processing {len(df)} active ISO 639-3 codes...")

        for _, row in df.iterrows():
            code = str(row.get("Id", "")).strip()
            if not code:
                continue

            languoid = self.get_or_create_languoid({IdType.ISO_639_3: code})

            ref_name = self._clean_optional(row.get("Ref_Name"))
            if ref_name:
                languoid.name = ref_name
                self._name_data[languoid.id] = [NameEntry(name=ref_name, bcp_47_code="en", is_canonical=True)]

            if part1 := self._clean_optional(row.get("Part1")):
                languoid.iso_639_1 = part1
                self.resolver.register_alias(IdType.ISO_639_1, part1, languoid.id)
                if self.resolver.resolve(IdType.BCP_47, part1) is None:
                    self.resolver.register_alias(IdType.BCP_47, part1, languoid.id)

            if part2b := self._clean_optional(row.get("Part2B")):
                languoid.iso_639_2b = part2b
                self.resolver.register_alias(IdType.ISO_639_2B, part2b, languoid.id)

            if part2t := self._clean_optional(row.get("Part2T")):
                self.resolver.register_alias(IdType.ISO_639_2T, part2t, languoid.id)

            scope = self._clean_optional(row.get("Scope"))
            if scope:
                languoid.scope = LanguageScope(scope)

            language_type = self._clean_optional(row.get("Language_Type"))
            if language_type:
                languoid.status = LanguageStatus(language_type)

        logger.info(f"Imported {len(df)} active ISO 639-3 codes")

    def _import_retirements(self, retirements_file: Path) -> None:
        """Import from SIL retirements TSV file."""
        import pandas as pd

        df = pd.read_csv(retirements_file, sep="\t").rename(columns=lambda col: col.strip())

        logger.info(f"Processing {len(df)} retired ISO 639-3 codes...")

        resolved_count = 0
        unresolved_count = 0

        for _, row in df.iterrows():
            retired_code = str(row.get("Id", "")).strip()
            if not retired_code:
                continue

            ref_name = self._clean_optional(row.get("Ref_Name"))
            ret_reason = self._clean_optional(row.get("Ret_Reason"))
            change_to = self._clean_optional(row.get("Change_To"))
            ret_remedy = self._clean_optional(row.get("Ret_Remedy"))
            effective = self._clean_optional(row.get("Effective"))

            if ret_reason == "S" and ret_remedy:
                split_into = self.tag_re.findall(ret_remedy)
            else:
                split_into = []

            reason_desc = self._format_reason(ret_reason, ret_remedy)
            self.resolver.register_deprecated(IdType.ISO_639_3, retired_code, reason_desc)

            if change_to:
                replacement_canonical = self.resolver.resolve(IdType.ISO_639_3, change_to)
                if replacement_canonical:
                    self.resolver.register_alias(IdType.ISO_639_3, retired_code, replacement_canonical)
                    languoid = self.resolve_languoid(IdType.ISO_639_3, change_to)
                    if languoid:
                        dc = DeprecatedCode(
                            code=retired_code,
                            code_type=IdType.ISO_639_3,
                            reason=DeprecationReason(ret_reason.upper()) if ret_reason else None,
                            name=ref_name,
                            effective=effective,
                            remedy=ret_remedy,
                        )
                        if languoid.deprecated_codes is None:
                            languoid.deprecated_codes = []
                        languoid.deprecated_codes.append(dc)
                        resolved_count += 1
                    else:
                        unresolved_count += 1
                else:
                    unresolved_count += 1
            elif split_into:
                for replacement_code in split_into:
                    replacement_canonical = self.resolver.resolve(IdType.ISO_639_3, replacement_code)
                    if not replacement_canonical:
                        continue
                    languoid = self.resolve_languoid(IdType.ISO_639_3, replacement_code)
                    if not languoid:
                        continue
                    dc = DeprecatedCode(
                        code=retired_code,
                        code_type=IdType.ISO_639_3,
                        reason=DeprecationReason.SPLIT,
                        name=ref_name,
                        effective=effective,
                        remedy=ret_remedy,
                        split_into=split_into,
                    )
                    if languoid.deprecated_codes is None:
                        languoid.deprecated_codes = []
                    languoid.deprecated_codes.append(dc)
                    resolved_count += 1
            else:
                unresolved_count += 1

        logger.info(
            f"SIL retirements: {resolved_count} resolved to replacements, {unresolved_count} without resolution"
        )

    @staticmethod
    def _format_reason(ret_reason: str | None, ret_remedy: str | None) -> str:
        """Format a human-readable reason string."""
        reason_map = {
            "C": "Change",
            "M": "Merge",
            "D": "Duplicate",
            "S": "Split",
            "N": "Non-existent",
        }
        label = reason_map.get(ret_reason or "", ret_reason or "Unknown")
        return f"{label}: {ret_remedy}" if ret_remedy else label

    @staticmethod
    def _clean_optional(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _find_file(data_path: Path, names: list[str]) -> Path | None:
        if data_path.is_file():
            return data_path if data_path.name in names else None
        for name in names:
            candidate = data_path / name
            if candidate.exists():
                return candidate
        return None
