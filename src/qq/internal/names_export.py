import json
import logging
import zipfile
from pathlib import Path

from qq.data_model import CanonicalId

logger = logging.getLogger(__name__)


class NamesExporter:
    """Exports name data to a single zip archive for efficient packaging."""

    def export_names(self, name_data_dict: dict[CanonicalId, list], output_path: Path) -> None:
        """
        Export name data to a single zip archive.

        Creates one zip file containing all name data as JSON files.
        Files inside the zip are named lang:XXXXXX.json (uncompressed JSON, zip handles compression).

        Args:
            name_data_dict: Dict mapping canonical ID -> list of name entries
            output_path: Path for the output zip file (e.g., src/qq/data/names.zip)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        exported_count = 0

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for entity_id, name_data in name_data_dict.items():
                if not name_data:
                    continue

                filename = f"{entity_id}.json"
                zf.writestr(filename, json.dumps(name_data, ensure_ascii=False))
                exported_count += 1

        logger.info(f"Exported names for {exported_count} languoids to {output_path}")


class NamesLoader:
    """Loads name data from a single zip archive."""

    def __init__(self, zip_path: Path):
        self.zip_path = Path(zip_path)
        self._zipfile = None

    def load_names(self, entity_id: CanonicalId) -> list[dict] | None:
        """
        Load name data for a specific languoid from the zip archive.

        Args:
            entity_id: Canonical entity ID (e.g., "lang:000001")

        Returns:
            List of name entries or None if not found.
            Each entry is a dict with keys: name, canonical_id, is_canonical, source.
        """
        if self._zipfile is None:
            if not self.zip_path.exists():
                logger.warning(f"Names zip file not found: {self.zip_path}")
                return None
            self._zipfile = zipfile.ZipFile(self.zip_path, "r")

        filename = f"{entity_id}.json"
        try:
            with self._zipfile.open(filename) as f:
                return json.load(f)
        except KeyError:
            return None
        except Exception as e:
            logger.warning(f"Failed to load names for {entity_id}: {e}")
            return None

    def close(self):
        """Close the zip file."""
        if self._zipfile is not None:
            self._zipfile.close()
            self._zipfile = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
