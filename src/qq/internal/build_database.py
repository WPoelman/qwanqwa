import logging
from pathlib import Path

from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge import merge
from qq.internal.storage import DataManager
from qq.sources.source_config import SourceConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# TODO: remove format, make it into an enum, or just get it from the path?
def build_database(sources_dir: Path, source_config: SourceConfig, output_dir: Path, format: str = "json.gz"):
    """Build the complete qwanqwa database from all sources."""
    logger.info("=" * 60)
    logger.info("Building qwanqwa database")
    logger.info("=" * 60)

    # Create shared entity resolver (for identity only)
    resolver = EntityResolver()

    # -- Import phase
    # Each importer fills its own EntitySet; they share only the resolver.
    importers = source_config.get_importers()
    to_merge = []
    for idx, (source_name, importer) in enumerate(importers.items()):
        logger.info(f"\n[{idx + 1}/{len(importers)}] Importing {source_name.title()}...")

        source_path = sources_dir / source_name  # TODO: can be nicer?
        imp = importer(resolver)
        imp.import_data(source_path)
        to_merge.append((importer.source, imp.entity_set))

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

    # TODO: add validator
    # validator = DataValidator(store, resolver)
    # validator.validate_all()

    # Log final statistics
    logger.info("Import complete!")
    logger.info(f"Total entities in store: {len(store._entities)}")

    entity_counts = {}
    for entity in store._entities.values():
        entity_type = entity.__class__.__name__
        entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

    for entity_type, count in entity_counts.items():
        logger.info(f"  {entity_type}: {count}")

    # TODO add separate extractors for name data, resolve and store here?
    # # Extract name data from LinguaMeta
    # name_data_dict = linguameta.name_data if separate_names else None

    # # Save the database
    logger.info(f"\nSaving database to {output_dir}...")
    manager = DataManager(format)
    manager.save_dataset(store, output_dir, resolver)

    logger.info("✓ Database built successfully!")
    return store, resolver
