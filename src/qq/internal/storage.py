import gzip
import json
import logging
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import qq
from qq.constants import DEFAULT_DB_PATH
from qq.internal.names_export import NamesExporter

if TYPE_CHECKING:
    from qq.data_model import TraversableEntity
    from qq.internal.data_store import DataStore
    from qq.internal.entity_resolution import EntityResolver

logger = logging.getLogger(__name__)

__all__ = [
    "DataManager",
    "load_data",
]


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def save(self, data: dict[str, Any], path: Path) -> None: ...

    @abstractmethod
    def load(self, path: Path) -> dict[str, Any]: ...


class JSONStorage(StorageBackend):
    """Store arbitrarily nested dict as json."""

    def save(self, data: dict[str, Any], path: Path) -> None:
        # Convert non-serializable objects to dicts
        serializable = self._make_serializable(data)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    def load(self, path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _make_serializable(self, obj) -> Any:
        """Convert objects to JSON-serializable format"""
        from enum import Enum

        if isinstance(obj, Enum):
            # Store enum as its value for JSON compatibility
            return obj.value
        elif hasattr(obj, "__dict__"):
            # Convert object to dict, include class name for reconstruction
            result = {"__class__": obj.__class__.__name__}
            result.update({k: self._make_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")})
            return result
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, set):
            return list(obj)
        else:
            return obj


class CompressedJSONStorage(JSONStorage):
    """Compress json database."""

    def save(self, data: dict[str, Any], path: Path) -> None:
        serializable = self._make_serializable(data)
        json_str = json.dumps(serializable, ensure_ascii=False)

        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(json_str)

    def load(self, path: Path) -> dict[str, Any]:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)


class PickleStorage(StorageBackend):
    """Pickle storage - fastest load/save."""

    def save(self, data: dict[str, Any], path: Path) -> None:
        with gzip.open(path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self, path: Path) -> dict[str, Any]:
        with gzip.open(path, "rb") as f:
            return pickle.load(f)


class DataManager:
    """
    Manages serialization/deserialization of the entire dataset.
    Supports multiple storage formats.
    """

    # TODO: this is bit stupid, maybe generate all for debugging (inspect json, load pickle)
    STORAGE_BACKENDS = {
        "json": JSONStorage(),
        "json.gz": CompressedJSONStorage(),
        "pkl.gz": PickleStorage(),
    }

    def __init__(self, storage_format: str = "pkl.gz"):
        self.storage_format = storage_format
        self.backend = self.STORAGE_BACKENDS[storage_format]

    def save_dataset(
        self,
        store: "DataStore",
        output_path: Path,
        resolver: "EntityResolver",
        name_data_dict: dict[str, list] | None = None,
    ) -> None:
        """
        Save entire DataStore to disk.

        Args:
            store: DataStore to save
            output_path: Path for main database file
            resolver: EntityResolver to save
            name_data_dict: Optional dict mapping canonical ID -> name data list.
                           If provided, exports names to a separate zip file.
        """
        data: dict[str, Any] = {
            "version": qq.__version__,
            "format": self.storage_format,
            "entities": {},
            "metadata": {
                "entity_count": len(store._entities),
                "entity_types": self._count_entity_types(store),
            },
        }

        for entity_id, entity in store._entities.items():
            data["entities"][entity_id] = self._serialize_entity(entity)

        data["resolver"] = self._serialize_resolver(resolver)

        logger.info(f"Saving {len(store._entities)} entities to {output_path}")
        self.backend.save(data, output_path)
        logger.info(f"Saved successfully ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")

        if name_data_dict:
            names_zip = output_path.parent / "names.zip"
            exporter = NamesExporter()
            exporter.export_names(name_data_dict, names_zip)

    def load_dataset(self, input_path: Path) -> "tuple[DataStore, EntityResolver]":
        """
        Load entire DataStore from disk.
        Reconstructs all entities and relationships.

        Returns:
            tuple: (DataStore, EntityResolver)
        """
        from qq.interface import GeographicRegion, Languoid, Script
        from qq.internal.data_store import DataStore

        input_path = Path(input_path)
        logger.debug(f"Loading dataset from {input_path}")

        data = self.backend.load(input_path)
        store = DataStore()

        entity_classes = {
            "Languoid": Languoid,
            "Script": Script,
            "GeographicRegion": GeographicRegion,
        }

        for entity_id, entity_data in data["entities"].items():
            entity_class_name = entity_data.get("__class__", "TraversableEntity")
            entity_class = entity_classes.get(entity_class_name)

            if entity_class:
                entity = self._deserialize_entity(entity_id, entity_data, entity_class, store)
                store.add(entity)

        logger.debug(f"Loaded {len(store._entities)} entities")

        resolver = self._deserialize_resolver(data["resolver"])
        return store, resolver

    def _serialize_entity(self, entity: "TraversableEntity") -> dict[str, Any]:
        """Convert entity to serializable dict."""
        from dataclasses import asdict, is_dataclass

        data: dict[str, Any] = {"__class__": entity.__class__.__name__, "id": entity.id, "relations": {}}

        for rel_type, relations in entity._relations.items():
            data["relations"][rel_type.value] = [
                {"target_id": rel.target_id, "metadata": rel.metadata} for rel in relations
            ]

        for key, value in entity.__dict__.items():
            if not key.startswith("_") and key != "id":
                if is_dataclass(value):
                    data[key] = asdict(value)
                elif isinstance(value, list) and value and is_dataclass(value[0]):
                    data[key] = [asdict(dc) for dc in value]
                else:
                    data[key] = value

        return data

    def _deserialize_entity(
        self, entity_id: str, data: dict[str, Any], entity_class: type, store: "DataStore"
    ) -> "TraversableEntity":
        """Reconstruct entity from dict"""
        import inspect

        from qq.data_model import DeprecatedCode, RelationType, WikipediaInfo

        # Get valid parameter names from entity class __init__
        sig = inspect.signature(entity_class.__init__)
        valid_params = set(sig.parameters.keys()) - {"self"}

        # Filter to only valid attributes
        attrs = {k: v for k, v in data.items() if k not in ["__class__", "id", "relations"] and k in valid_params}

        # Reconstruct WikipediaInfo from dict
        if "wikipedia" in attrs and isinstance(attrs["wikipedia"], dict):
            attrs["wikipedia"] = WikipediaInfo(**attrs["wikipedia"])

        # Reconstruct DeprecatedCode list from dicts
        if "deprecated_codes" in attrs and isinstance(attrs["deprecated_codes"], list):
            attrs["deprecated_codes"] = [
                DeprecatedCode(**dc) if isinstance(dc, dict) else dc for dc in attrs["deprecated_codes"]
            ]

        entity = entity_class(entity_id, store, **attrs)

        if "relations" in data:
            for rel_type_str, relations in data["relations"].items():
                rel_type = RelationType(rel_type_str)
                for rel_data in relations:
                    entity.add_relation(rel_type, rel_data["target_id"], **rel_data.get("metadata", {}))

        return entity

    def _count_entity_types(self, store: "DataStore") -> dict[str, int]:
        """Count entities by type"""
        from collections import Counter

        return dict(Counter(e.__class__.__name__ for e in store._entities.values()))

    def _serialize_resolver(self, resolver: "EntityResolver") -> dict[str, Any]:
        """Serialize EntityResolver to dict"""
        # Convert tuple keys to string keys for JSON serialization
        id_to_canonical = {
            f"{id_type.value}:{value}": canonical_id
            for (id_type, value), canonical_id in resolver._id_to_canonical.items()
        }

        identities = {}
        for canonical_id, identity in resolver._identities.items():
            identities[canonical_id] = {
                "identifiers": {id_type.value: value for id_type, value in identity.identifiers.items()},
            }

        # Serialize deprecated codes
        deprecated_codes = {
            f"{id_type.value}:{value}": reason for (id_type, value), reason in resolver._deprecated_codes.items()
        }

        return {
            "id_to_canonical": id_to_canonical,
            "identities": identities,
            "next_id": resolver._next_id,
            "deprecated_codes": deprecated_codes,
        }

    def _deserialize_resolver(self, data: dict[str, Any]) -> "EntityResolver":
        """Deserialize EntityResolver from dict"""
        from qq.internal.entity_resolution import EntityIdentity, EntityResolver, IdType

        resolver = EntityResolver()

        resolver._next_id = data.get("next_id", 1)

        for canonical_id, identity_data in data.get("identities", {}).items():
            identity = EntityIdentity(canonical_id)
            for id_type_value, value in identity_data.get("identifiers", {}).items():
                id_type = IdType(id_type_value)
                identity.identifiers[id_type] = value
            resolver._identities[canonical_id] = identity

        for key, canonical_id in data.get("id_to_canonical", {}).items():
            # "id_type:value" format to tuple
            id_type_value, value = key.split(":", 1)
            id_type = IdType(id_type_value)
            resolver._id_to_canonical[(id_type, value)] = canonical_id

        # Restore deprecated codes
        for key, reason in data.get("deprecated_codes", {}).items():
            id_type_value, value = key.split(":", 1)
            id_type = IdType(id_type_value)
            resolver._deprecated_codes[(id_type, value)] = reason

        return resolver


def load_data(path: Path = DEFAULT_DB_PATH):
    """
    Load both DataStore and EntityResolver.

    Convenience wrapper around DataManager.load_dataset that auto-detects
    storage format from file extension.
    """
    path_obj = Path(path)

    # Determine storage format from extension
    if str(path_obj).endswith(".json.gz"):
        manager = DataManager("json.gz")
    elif str(path_obj).endswith(".pkl.gz"):
        manager = DataManager("pkl.gz")
    else:
        manager = DataManager("json")

    return manager.load_dataset(path_obj)
