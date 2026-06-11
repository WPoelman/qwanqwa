from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from qq.data_model import DataSource
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


class UnicodeImporter(BaseImporter):
    """Enrich script entities with Unicode script ranges."""

    source = DataSource.UNICODE

    def import_data(self, data_path: Path) -> None:
        aliases_path = data_path / "PropertyValueAliases.txt"
        scripts_path = data_path / "Scripts.txt"
        if not aliases_path.exists() or not scripts_path.exists():
            raise FileNotFoundError("Unicode UCD source is missing Scripts.txt or PropertyValueAliases.txt")

        alias_to_iso = self._load_script_aliases(aliases_path)
        ranges_by_iso, counts_by_iso = self._load_script_ranges(scripts_path, alias_to_iso)

        enriched = 0
        for iso_15924, ranges in ranges_by_iso.items():
            script = self.get_or_create_script(f"script:{iso_15924.lower()}")
            script.iso_15924 = iso_15924
            script.unicode_alias = self._iso_to_alias(alias_to_iso, iso_15924)
            script.unicode_ranges = ranges
            script.unicode_character_count = counts_by_iso[iso_15924]
            enriched += 1

        logger.info("Imported Unicode ranges for %d scripts", enriched)
        self.stats.entities_updated += enriched
        self.log_stats()

    def _load_script_aliases(self, path: Path) -> dict[str, str]:
        alias_to_iso: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            content = line.split("#", 1)[0].strip()
            if not content:
                continue
            fields = [field.strip() for field in content.split(";")]
            if len(fields) < 3 or fields[0] != "sc":
                continue
            iso_15924 = fields[1]
            for alias in fields[1:]:
                if alias:
                    alias_to_iso[alias] = iso_15924
        return alias_to_iso

    def _load_script_ranges(
        self, path: Path, alias_to_iso: dict[str, str]
    ) -> tuple[dict[str, list[str]], dict[str, int]]:
        ranges_by_iso: dict[str, list[str]] = defaultdict(list)
        counts_by_iso: dict[str, int] = defaultdict(int)

        for line in path.read_text(encoding="utf-8").splitlines():
            content = line.split("#", 1)[0].strip()
            if not content or ";" not in content:
                continue
            range_text, script_alias = [field.strip() for field in content.split(";", 1)]
            iso_15924 = alias_to_iso.get(script_alias)
            if not iso_15924:
                continue
            ranges_by_iso[iso_15924].append(self._format_range(range_text))
            counts_by_iso[iso_15924] += self._range_size(range_text)

        return dict(ranges_by_iso), dict(counts_by_iso)

    @staticmethod
    def _iso_to_alias(alias_to_iso: dict[str, str], iso_15924: str) -> str | None:
        for alias, code in alias_to_iso.items():
            if code == iso_15924 and alias != iso_15924:
                return alias
        return None

    @staticmethod
    def _format_range(range_text: str) -> str:
        if ".." not in range_text:
            return f"U+{range_text}"
        start, end = range_text.split("..", 1)
        return f"U+{start}..U+{end}"

    @staticmethod
    def _range_size(range_text: str) -> int:
        if ".." not in range_text:
            return 1
        start, end = range_text.split("..", 1)
        return int(end, 16) - int(start, 16) + 1
