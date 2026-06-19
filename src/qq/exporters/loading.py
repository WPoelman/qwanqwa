from pathlib import Path

from qq.data_model import NameEntry
from qq.exporters.context import ExportContext, ProvenanceRecord
from qq.internal.names_export import NamesLoader


def context_from_loaded(store, resolver, database_path: Path, load_names: bool = False) -> ExportContext:
    raw = getattr(store, "_export_metadata", {})
    names_path = database_path.parent / "names.zip"
    names: dict[str, list[NameEntry]] = {}
    if load_names and names_path.exists():
        with NamesLoader(names_path) as loader:
            names = loader.load_all()
    context = ExportContext(
        store=store,
        resolver=resolver,
        names=names,
        source_metadata=raw.get("source_metadata", {}),
        provenance=[ProvenanceRecord(**item) for item in raw.get("provenance", [])],
        qq_version=raw.get("qq_version") or raw.get("version") or "unknown",
        build_metadata=raw.get("build_metadata", {}),
    )
    return context.attach()


def load_export_context(database_path: Path) -> ExportContext:
    from qq.internal.storage import load_data

    database_path = Path(database_path)
    store, resolver = load_data(database_path)
    context = getattr(store, "export_context", None)
    if context is not None and context.names:
        return context
    return context_from_loaded(store, resolver, database_path, load_names=True)
