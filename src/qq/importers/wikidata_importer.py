from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from qq.data_model import DataSource, IdType
from qq.importers.base_importer import BaseImporter

logger = logging.getLogger(__name__)


class WikidataIso6395Importer(BaseImporter):
    """Import ISO 639-5 codes that can be linked to Glottolog families through glottocodes."""

    source = DataSource.WIKIDATA

    def import_data(self, data_path: Path) -> None:
        if not data_path.exists():
            raise FileNotFoundError(f"Wikidata ISO 639-5 data not found: {data_path}")

        data = json.loads(data_path.read_text(encoding="utf-8"))
        rows_by_code = self._rows_by_iso6395(data)
        linked = 0
        skipped_ambiguous = 0
        skipped_without_glottocode = 0
        skipped_unresolved = 0

        for iso6395, rows in rows_by_code.items():
            glottocodes = {row["glottocode"] for row in rows if row.get("glottocode")}
            if not glottocodes:
                skipped_without_glottocode += 1
                continue
            if len(glottocodes) > 1:
                logger.warning("Skipping ambiguous ISO 639-5 Wikidata mapping for %s: %s", iso6395, sorted(glottocodes))
                skipped_ambiguous += 1
                continue

            glottocode = next(iter(glottocodes))
            canonical_id = self.resolver.resolve(IdType.GLOTTOCODE, glottocode)
            if not canonical_id:
                skipped_unresolved += 1
                continue

            self.resolver.register_alias(IdType.ISO_639_5, iso6395, canonical_id)
            wikidata_ids = {row["wikidata_id"] for row in rows if row.get("wikidata_id")}
            if len(wikidata_ids) == 1 and not self.resolver.resolve(IdType.WIKIDATA_ID, next(iter(wikidata_ids))):
                self.resolver.register_alias(IdType.WIKIDATA_ID, next(iter(wikidata_ids)), canonical_id)

            languoid = self.resolve_languoid(IdType.GLOTTOCODE, glottocode)
            if languoid:
                languoid.iso_639_5 = iso6395
                if len(wikidata_ids) == 1 and not languoid.wikidata_id:
                    languoid.wikidata_id = next(iter(wikidata_ids))
                linked += 1

        logger.info(
            "Linked %d ISO 639-5 codes via Wikidata (%d without Glottocode, %d ambiguous, %d unresolved)",
            linked,
            skipped_without_glottocode,
            skipped_ambiguous,
            skipped_unresolved,
        )
        self.log_stats()

    @staticmethod
    def _rows_by_iso6395(data: dict) -> dict[str, list[dict[str, str]]]:
        rows_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
        for binding in data.get("results", {}).get("bindings", []):
            iso6395 = binding.get("iso6395", {}).get("value")
            if not iso6395:
                continue
            item = binding.get("item", {}).get("value", "")
            row = {
                "iso6395": iso6395,
                "wikidata_id": item.rsplit("/", 1)[-1] if item else "",
                "label": binding.get("itemLabel", {}).get("value", ""),
                "glottocode": binding.get("glottocode", {}).get("value", ""),
            }
            rows_by_code[iso6395].append(row)
        return dict(rows_by_code)


class WikidataScriptMetadataImporter(BaseImporter):
    """Enrich ISO 15924 scripts with selected Wikidata metadata."""

    source = DataSource.WIKIDATA

    _TYPE_PRIORITY = {
        "Q1191127": (0, "featural"),
        "Q3781304": (1, "semi-syllabary"),
        "Q335806": (2, "abugida"),
        "Q185087": (3, "abjad"),
        "Q182133": (4, "syllabary"),
        "Q3953107": (5, "logographic"),
        "Q9779": (6, "alphabet"),
        "Q2182919": (7, "alphabet"),
    }

    def import_data(self, data_path: Path) -> None:
        if not data_path.exists():
            raise FileNotFoundError(f"Wikidata script metadata not found: {data_path}")

        data = json.loads(data_path.read_text(encoding="utf-8"))
        rows_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for binding in data.get("results", {}).get("bindings", []):
            code = binding.get("iso15924", {}).get("value", "")
            if len(code) != 4 or code.lower().startswith("qa"):
                continue
            rows_by_code[code].append(binding)

        enriched = 0
        for code, rows in rows_by_code.items():
            script = self.get_or_create_script(f"script:{code.lower()}")
            script.iso_15924 = code
            script.script_type = self._select_type(rows)
            script.family = self._select_text(rows, "familyLabel")
            script.sample = self._select_sample(rows)
            enriched += 1

        logger.info("Enriched %d scripts with Wikidata metadata", enriched)
        self.log_stats()

    @classmethod
    def _select_type(cls, rows: list[dict[str, Any]]) -> str | None:
        candidates = []
        for row in rows:
            uri = row.get("type", {}).get("value", "")
            qid = uri.rsplit("/", 1)[-1]
            if qid in cls._TYPE_PRIORITY:
                candidates.append(cls._TYPE_PRIORITY[qid])
        return min(candidates)[1] if candidates else None

    @staticmethod
    def _select_text(rows: list[dict[str, Any]], key: str) -> str | None:
        values = {row.get(key, {}).get("value", "").strip() for row in rows}
        values.discard("")
        return min(values, key=lambda value: (len(value), value.casefold())) if values else None

    @classmethod
    def _select_sample(cls, rows: list[dict[str, Any]]) -> str | None:
        values = {
            row.get("sample", {}).get("value", "").strip()
            for row in rows
            if len(row.get("sample", {}).get("value", "").strip()) <= 80
        }
        values.discard("")
        return min(values, key=lambda value: (len(value), value.casefold())) if values else None
