from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import qq
from qq.data_model import NameEntry
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver


@dataclass
class ProvenanceRecord:
    """Attribution for a merged field, relation, or multilingual name."""

    kind: str
    entity_id: str
    source_name: str
    role: str
    field_name: str | None = None
    relation_type: str | None = None
    target_id: str | None = None
    strategy: str | None = None
    value: Any = None
    metadata: dict[str, Any] | None = None
    priority: int | None = None


@dataclass
class ExportContext:
    """Canonical, exporter-independent snapshot of a QQ build."""

    store: DataStore
    resolver: EntityResolver
    names: dict[str, list[NameEntry]] = field(default_factory=dict)
    source_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    provenance: list[ProvenanceRecord] = field(default_factory=list)
    qq_version: str = field(default_factory=lambda: qq.__version__)
    build_metadata: dict[str, Any] = field(default_factory=dict)

    def attach(self) -> "ExportContext":
        self.store.export_context = self
        return self

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "qq_version": self.qq_version,
            "build_metadata": self.build_metadata,
            "source_metadata": self.source_metadata,
            "provenance": [asdict(record) for record in self.provenance],
        }
