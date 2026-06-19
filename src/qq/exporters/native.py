from pathlib import Path

from qq.exporters.context import ExportContext
from qq.internal.storage import DataManager


class NativeExporter:
    name = "native"

    def __init__(self, storage_format: str = "json.gz") -> None:
        self.storage_format = storage_format

    def export(self, context: ExportContext, output_path: Path) -> Path:
        output_path = Path(output_path)
        if output_path.name.endswith((".json", ".json.gz", ".pkl.gz")):
            database_path = output_path
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            database_path = output_path / f"db.{self.storage_format}"
        database_path.parent.mkdir(parents=True, exist_ok=True)
        context.attach()
        DataManager(self.storage_format).save_dataset(context.store, database_path, context.resolver, context.names)
        return database_path
