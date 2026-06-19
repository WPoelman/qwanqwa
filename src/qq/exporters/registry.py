from __future__ import annotations

from pathlib import Path
from typing import Protocol

from qq.exporters.context import ExportContext


class Exporter(Protocol):
    name: str

    def export(self, context: ExportContext, output_path: Path) -> Path: ...


_EXPORTERS: dict[str, Exporter] = {}


def register_exporter(exporter: Exporter) -> None:
    name = exporter.name.strip().lower()
    if not name:
        raise ValueError("Exporter name cannot be empty")
    if name in _EXPORTERS:
        raise ValueError(f"Exporter '{name}' is already registered")
    _EXPORTERS[name] = exporter


def get_exporter(name: str) -> Exporter:
    normalized = name.strip().lower()
    try:
        return _EXPORTERS[normalized]
    except KeyError as exc:
        available = ", ".join(list_exporters())
        raise KeyError(f"Unknown exporter '{name}'. Available exporters: {available}") from exc


def list_exporters() -> list[str]:
    return sorted(_EXPORTERS)


def export(name: str, context: ExportContext, output_path: Path) -> Path:
    return get_exporter(name).export(context, Path(output_path))
