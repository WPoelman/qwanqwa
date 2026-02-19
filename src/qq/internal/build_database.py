import logging
from pathlib import Path
from typing import Literal

from qq.constants import LOG_SEP
from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge import merge
from qq.internal.names_merge import merge_name_data, resolve_locale_codes
from qq.internal.storage import DataManager
from qq.internal.validation import DataValidator
from qq.sources.source_config import SourceConfig

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def build_database(
    sources_dir: Path,
    source_config: SourceConfig,
    output_dir: Path,
    format: Literal["json.gz", "json", "pkl.gz"] = "json.gz",
):
    """Build the complete qwanqwa database from all sources."""
    logger.info(LOG_SEP)
    logger.info("Building qwanqwa database")
    logger.info(LOG_SEP)

    # Create shared entity resolver (for identity only)
    resolver = EntityResolver()

    # -- Import phase
    # Each importer fills its own EntitySet; they share only the resolver.
    importers = source_config.get_importers()
    to_merge = []
    instances = []
    for idx, (source_name, importer_cls) in enumerate(importers):
        logger.info(f"[{idx + 1}/{len(importers)}] Importing {source_name.title()}...")

        source_path = sources_dir / source_name  # TODO: can be nicer?
        imp = importer_cls(resolver)
        imp.import_data(source_path)
        to_merge.append((importer_cls.source, imp.entity_set))
        instances.append(imp)

    # -- Merge phase
    # Combine all per-source EntitySets into the final DataStore.
    logger.info("Merging entity sets into final DataStore")
    conflicts_file = output_dir / "conflicts.json"
    store = merge(to_merge, conflicts_file)

    # Log entity resolution statistics
    logger.info("Entity Resolution Statistics:")
    resolver_stats = resolver.stats()
    logger.info(f"Total unique entities: {resolver_stats['total_entities']}")
    logger.info(f"Total identifier mappings: {resolver_stats['total_identifier_mappings']}")

    logger.info("Running data validation...")

    validator = DataValidator(store, resolver)
    validator.validate_all()

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

    logger.info("✓ Database built successfully!")
    return store, resolver
