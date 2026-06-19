from pathlib import Path

from qq.exporters.context import ExportContext


class DemoExporter:
    name = "demo"

    def export(self, context: ExportContext, output_path: Path) -> Path:
        from qq.explorer.export import export_demo_data

        return export_demo_data(output_path, context=context)
