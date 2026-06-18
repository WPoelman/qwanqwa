import logging
from pathlib import Path
from typing import Literal

from qq.constants import LOG_SEP
from qq.data_model import ID_TYPE_TO_ATTR
from qq.importers.base_importer import DataSource, EntitySet
from qq.interface import Languoid
from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge import merge
from qq.internal.names_merge import merge_name_data, remap_name_data_keys, resolve_locale_codes
from qq.internal.storage import DataManager
from qq.internal.validation import DataValidator
from qq.sources.source_config import SourceConfig

logger = logging.getLogger(__name__)


def _reconcile_merged_languoids(
    sources: list[tuple[DataSource, EntitySet]], resolver: EntityResolver
) -> dict[str, str]:
    """Rewrite stale languoid IDs in importer entity sets after resolver merges."""
    reconciled: dict[str, str] = {}

    for _source, entity_set in sources:
        stale_ids = [
            lang.id for lang in entity_set.entities_of_type(Languoid) if resolver.get_identity(lang.id) is None
        ]
        for stale_id in stale_ids:
            languoid = entity_set.get(stale_id)
            if not isinstance(languoid, Languoid):
                continue

            target_id = None
            for id_type, attr_name in ID_TYPE_TO_ATTR.items():
                value = getattr(languoid, attr_name, None)
                if not value:
                    continue
                resolved_id = resolver.resolve(id_type, value)
                if resolved_id is not None:
                    target_id = resolved_id
                    break

            if target_id is None or target_id == stale_id:
                continue

            entity_set.merge_entity_ids(stale_id, target_id)
            reconciled[stale_id] = target_id

    return reconciled


def build_database(
    source_config: SourceConfig,
    output_dir: Path,
    format: Literal["json.gz", "json", "pkl.gz"] = "json.gz",
):
    """Build the complete qwanqwa database from all sources."""
    logger.info(LOG_SEP)
    logger.info("Building qwanqwa database")
    logger.info(LOG_SEP)

    # Dir to store validation results, merge conflicts, etc.
    build_log_dir = output_dir / "build-log"
    build_log_dir.mkdir(exist_ok=True, parents=True)

    # Create shared entity resolver (for identity only)
    resolver = EntityResolver()

    # -- Import phase
    # Each importer fills its own EntitySet; they share only the resolver.
    importers = source_config.get_importers()
    to_merge = []
    instances = []
    for idx, importer_config in enumerate(importers):
        display_name = importer_config.source_name.replace("_", " ").title()
        logger.info(f"[{idx + 1}/{len(importers)}] Importing {display_name}...")

        source_path = importer_config.resolve_data_path(source_config.sources_dir)
        imp = importer_config.importer_cls(resolver, **importer_config.kwargs)
        imp.import_data(source_path)
        to_merge.append((importer_config.importer_cls.source, imp.entity_set))
        instances.append(imp)

    # -- Merge phase
    # Combine all per-source EntitySets into the final DataStore.
    reconciled = _reconcile_merged_languoids(to_merge, resolver)
    if reconciled:
        logger.info(f"Reconciled {len(reconciled)} stale languoid IDs across importer entity sets")
        for imp in instances:
            if hasattr(imp, "name_data") and imp.name_data:
                remapped = remap_name_data_keys(imp.name_data, reconciled)
                imp.name_data.clear()
                imp.name_data.update(remapped)

    logger.info("Merging entity sets into final DataStore")
    conflicts_file = build_log_dir / "conflicts.json"
    store = merge(to_merge, conflicts_file)

    # Log entity resolution statistics
    logger.info("Entity Resolution Statistics:")
    resolver_stats = resolver.stats()
    logger.info(f"Total unique entities: {resolver_stats['total_entities']}")
    logger.info(f"Total identifier mappings: {resolver_stats['total_identifier_mappings']}")

    logger.info("Running data validation...")

    validation_file = build_log_dir / "validation-results.json"
    validator = DataValidator(store, resolver)
    validator.validate_all(validation_file)

    # Log final statistics
    logger.info("Import complete!")
    logger.info(f"Total entities in store: {len(store._entities)}")

    entity_counts = {}
    for entity in store._entities.values():
        entity_type = entity.__class__.__name__
        entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

    for entity_type, count in entity_counts.items():
        logger.info(f"  {entity_type}: {count}")

    # Collect and merge name data from all importers
    all_name_data = [imp.name_data for imp in instances if hasattr(imp, "name_data") and imp.name_data]
    if all_name_data:
        name_data_dict = merge_name_data(all_name_data)
        name_data_dict = resolve_locale_codes(name_data_dict, resolver)
    else:
        name_data_dict = None

    # Save the database
    output_path = output_dir / f"db.{format}"
    logger.info(f"Saving database to {output_path}...")
    manager = DataManager(format)
    manager.save_dataset(store, output_path, resolver, name_data_dict)

    return store, resolver
