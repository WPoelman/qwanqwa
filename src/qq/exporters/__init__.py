from qq.exporters.context import ExportContext, ProvenanceRecord
from qq.exporters.registry import Exporter, register_exporter


def _register_builtins() -> None:
    from qq.exporters.cldf import CLDFExporter
    from qq.exporters.demo import DemoExporter
    from qq.exporters.native import NativeExporter
    from qq.exporters.registry import list_exporters as _listed

    existing = set(_listed())
    for exporter in (NativeExporter(), DemoExporter(), CLDFExporter()):
        if exporter.name not in existing:
            register_exporter(exporter)


def list_exporters():
    _register_builtins()
    from qq.exporters.registry import list_exporters as implementation

    return implementation()


def get_exporter(name):
    _register_builtins()
    from qq.exporters.registry import get_exporter as implementation

    return implementation(name)


def export(name, context, output_path):
    return get_exporter(name).export(context, output_path)


__all__ = [
    "ExportContext",
    "Exporter",
    "ProvenanceRecord",
    "export",
    "get_exporter",
    "list_exporters",
    "register_exporter",
]
