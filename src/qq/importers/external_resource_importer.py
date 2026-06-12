from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from qq.data_model import DataSource, ExternalResource
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid
from qq.sources.external_resource import ExternalResourceDefinition, ExternalResourceFileFormat

logger = logging.getLogger(__name__)


class ExternalResourceImporter(BaseImporter):
    """Attach external resource links to existing languoids.

    Sources and configs are in ``SourceConfig``. This
    importer only knows how to resolve dataset / column identifiers to languoids
    and attach an ``ExternalResource`` record to them.
    """

    source = DataSource.EXTERNAL_RESOURCES

    def __init__(self, resolver, definitions: list[ExternalResourceDefinition]):
        super().__init__(resolver)
        self.definitions = definitions

    def import_data(self, data_path: Path) -> None:
        total = 0
        for definition in self.definitions:
            if definition.source_name is None:
                total += self._import_identifier_resource(definition)
            else:
                total += self._import_table_resource(data_path, definition)
        logger.info("Attached %d external resource links", total)
        self.log_stats()

    def _import_identifier_resource(self, definition: ExternalResourceDefinition) -> int:
        if definition.match_column is None or definition.match_id_type is None:
            return 0

        added = 0
        for identity in self.resolver.identities():
            code = identity.get_identifier(definition.match_id_type)
            if not code:
                continue
            lang = self._get_languoid(identity.canonical_id)
            if self._add_resource(lang, definition, code, match_value=code):
                added += 1
        return added

    def _import_table_resource(self, sources_dir: Path, definition: ExternalResourceDefinition) -> int:
        if (
            not definition.source_name
            or not definition.filename
            or not definition.match_column
            or not definition.match_id_type
        ):
            return 0

        path = sources_dir / definition.source_name / definition.filename
        if not path.exists():
            logger.warning("External resource source missing: %s", path)
            return 0

        added = 0
        for match_value, code, count in self._iter_source_codes(path, definition):
            canonical_id = self.resolver.resolve(definition.match_id_type, match_value)
            if not canonical_id:
                continue
            lang = self._get_languoid(canonical_id)
            if self._add_resource(lang, definition, code, count, match_value=match_value):
                added += 1
        return added

    def _iter_source_codes(self, path: Path, definition: ExternalResourceDefinition):
        if definition.file_format is ExternalResourceFileFormat.CSV:
            yield from self._iter_csv_source_codes(path, definition)
        elif definition.file_format is ExternalResourceFileFormat.DSPACE_ITEM_JSON:
            yield from self._iter_dspace_item_json_source_codes(path, definition)
        elif definition.file_format is ExternalResourceFileFormat.HUGGINGFACE_TAGS_JSON:
            yield from self._iter_huggingface_tags_json_source_codes(path, definition)

    def _iter_csv_source_codes(self, path: Path, definition: ExternalResourceDefinition):
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

        if definition.unique_per_languoid:
            rows = self._prefer_plain_named_rows(rows, definition)

        for row in rows:
            match_value = (row.get(definition.match_column or "") or "").strip()
            if not match_value:
                continue
            code_column = definition.code_column or definition.match_column
            code = (row.get(code_column or "") or match_value).strip()
            if code:
                yield match_value, code, None

    def _prefer_plain_named_rows(
        self, rows: list[dict[str, str]], definition: ExternalResourceDefinition
    ) -> list[dict[str, str]]:
        best_rows: dict[str, dict[str, str]] = {}
        for row in rows:
            match_value = (row.get(definition.match_column or "") or "").strip()
            if not match_value:
                continue
            current = best_rows.get(match_value)
            if current is None or self._is_plain_name(row) and not self._is_plain_name(current):
                best_rows[match_value] = row
        return list(best_rows.values())

    @staticmethod
    def _is_plain_name(row: dict[str, str]) -> bool:
        name = (row.get("Name") or "").strip()
        return bool(name) and "(" not in name and ")" not in name

    def _iter_dspace_item_json_source_codes(self, path: Path, definition: ExternalResourceDefinition):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("metadata", {}).get(definition.match_column or "", []):
            match_value = (item.get("value") or "").strip()
            if match_value:
                yield match_value, match_value, None

    def _iter_huggingface_tags_json_source_codes(self, path: Path, definition: ExternalResourceDefinition):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("language", []):
            if not isinstance(item, dict):
                continue
            tag_id = item.get("id")
            if not isinstance(tag_id, str) or not tag_id.startswith("language:"):
                continue
            code = tag_id.removeprefix("language:").strip()
            count = item.get("dataset_count")
            if code:
                yield code, code, count if isinstance(count, int) else None

    def _get_languoid(self, canonical_id: str) -> Languoid:
        entity = self.entity_set.get(canonical_id)
        if isinstance(entity, Languoid):
            self.stats.entities_updated += 1
            return entity

        identity = self.resolver.get_identity(canonical_id)
        kwargs = self._identifiers_to_kwargs(identity) if identity else {}
        languoid = Languoid(canonical_id, self.entity_set, **kwargs)
        self.entity_set.add(languoid)
        self.stats.entities_created += 1
        return languoid

    def _add_resource(
        self,
        lang: Languoid,
        definition: ExternalResourceDefinition,
        code: str,
        count: int | None = None,
        match_value: str | None = None,
    ) -> bool:
        url = definition.url_template.format(code=code)
        if any(resource.url == url for resource in lang.external_resources):
            return False
        if definition.unique_per_languoid and any(
            resource.label == definition.label for resource in lang.external_resources
        ):
            return False

        lang.external_resources.append(
            ExternalResource(
                label=definition.label,
                group=definition.group,
                code=code,
                url=url,
                count=count,
                source_name=definition.source_name or "qq",
                source_file=definition.filename,
                match_column=definition.match_column,
                match_id_type=definition.match_id_type,
                match_value=match_value,
                code_column=definition.code_column,
            )
        )
        return True
