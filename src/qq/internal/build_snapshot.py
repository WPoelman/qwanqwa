from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import qq
from qq.data_model import NameEntry
from qq.exporters.context import ExportContext, ProvenanceRecord


def source_metadata_from_config(source_config) -> dict[str, dict[str, Any]]:
    metadata = {}
    for provider in source_config.get_providers(source_config.sources_dir):
        item = provider.metadata
        metadata[provider.name] = {
            "name": provider.name,
            "display_name": provider.display_name,
            "source_url": item.source_url,
            "website_url": item.website_url,
            "paper_url": item.paper_url,
            "license": item.license,
            "source_type": item.source_type.value,
            "version": item._version or provider.get_version(),
            "last_updated": item._last_updated.isoformat() if item._last_updated else None,
            "last_checked": item._last_checked.isoformat() if item._last_checked else None,
            "checksum": item._checksum,
            "notes": item.notes,
        }
    return metadata


def attribute_name_data(
    importer_instances: list[tuple[str, object]],
) -> tuple[list[dict[str, list[NameEntry]]], list[ProvenanceRecord]]:
    all_name_data = []
    provenance = []
    for source_name, importer in importer_instances:
        raw = getattr(importer, "name_data", None)
        if not raw:
            continue
        attributed = {}
        for entity_id, entries in raw.items():
            attributed[entity_id] = [
                entry if entry.source_name else replace(entry, source_name=source_name) for entry in entries
            ]
            provenance.extend(
                ProvenanceRecord(
                    kind="name",
                    entity_id=entity_id,
                    source_name=source_name,
                    role="contributor",
                    field_name="name",
                    value=entry.name,
                    metadata={
                        "bcp_47_code": entry.bcp_47_code,
                        "locale_id": entry.locale_id,
                        "is_canonical": entry.is_canonical,
                    },
                )
                for entry in attributed[entity_id]
            )
        all_name_data.append(attributed)
    return all_name_data, provenance


def make_export_context(store, resolver, names, source_config, name_provenance) -> ExportContext:
    return ExportContext(
        store=store,
        resolver=resolver,
        names=names or {},
        source_metadata=source_metadata_from_config(source_config),
        provenance=[*getattr(store, "provenance", []), *name_provenance],
        qq_version=qq.__version__,
        build_metadata={"built_at": datetime.now(timezone.utc).isoformat(), "format_version": 2},
    ).attach()
