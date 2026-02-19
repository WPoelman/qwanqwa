import logging
import re
from pathlib import Path

from qq.data_model import DataSource, DeprecatedCode, DeprecationReason, IdType
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


class SILImporter(BaseImporter):
    """Import ISO 639-3 retirements data from SIL.

    Parses the SIL retirements TSV to track deprecated/retired ISO 639-3 codes.
    For codes with replacements (reasons C/M/D), registers the old code as an
    alias pointing to the replacement languoid. For all retired codes, registers
    them in the resolver's deprecated code tracking.
    """

    source = DataSource.SIL

    tag_re = re.compile(r"\[([a-z]{3})\]")

    def import_data(self, data_path: Path) -> None:
        """Import from SIL retirements TSV file."""
        import pandas as pd

        retirements_file = data_path / "iso_639_3_retirements.tab"

        df = pd.read_csv(retirements_file, sep="\t").rename(columns=lambda col: col.strip())

        logger.info(f"Processing {len(df)} retired ISO 639-3 codes...")

        resolved_count = 0
        unresolved_count = 0

        for _, row in df.iterrows():
            retired_code = str(row.get("Id", "")).strip()
            if not retired_code:
                continue

            ref_name = row.get("Ref_Name")
            ref_name = ref_name.strip() if isinstance(ref_name, str) else None

            ret_reason = row.get("Ret_Reason")
            ret_reason = ret_reason.strip() if isinstance(ret_reason, str) else None

            change_to = row.get("Change_To")
            change_to = change_to.strip() or None if isinstance(change_to, str) else None

            ret_remedy = row.get("Ret_Remedy")
            ret_remedy = ret_remedy.strip() if isinstance(ret_remedy, str) else None

            effective = row.get("Effective")
            effective = effective.strip() if isinstance(effective, str) else None

            if ret_reason == "S" and ret_remedy:  # Split into new codes
                split_into = self.tag_re.findall(ret_remedy)
            else:
                split_into = []

            reason_desc = self._format_reason(ret_reason, ret_remedy)
            self.resolver.register_deprecated(IdType.ISO_639_3, retired_code, reason_desc)

            if change_to:
                # Has a replacement: find the replacement languoid and attach
                replacement_canonical = self.resolver.resolve(IdType.ISO_639_3, change_to)
                if replacement_canonical:
                    # Register old code as alias pointing to replacement
                    self.resolver.register_alias(IdType.ISO_639_3, retired_code, replacement_canonical)
                    # Create stub languoid in our EntitySet and add DeprecatedCode
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
                # Register split: attach DeprecatedCode to each replacement languoid
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
                # No replacement (Non-existent)
                unresolved_count += 1

        logger.info(
            f"SIL retirements: {resolved_count} resolved to replacements, {unresolved_count} without resolution"
        )
        self.log_stats()

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
