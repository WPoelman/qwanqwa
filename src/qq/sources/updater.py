import logging
from pathlib import Path

from qq.constants import LOG_SEP
from qq.sources.providers import SourceStatus
from qq.sources.source_config import SourceConfig

logger = logging.getLogger(__name__)


class SourceUpdater:
    """Manages updating all data sources and rebuilding the database"""

    def __init__(self, sources_dir: Path):
        self.sources_dir = sources_dir
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.providers = SourceConfig.get_providers_as_dict(self.sources_dir)

    def update_all(self, force: bool = False, rebuild: bool = True) -> dict[str, bool]:
        """
        Update all data sources.

        Args:
            force: Force update even if sources appear up-to-date
            rebuild: Rebuild database after updating sources

        Returns:
            Dict mapping source name to whether it was updated
        """
        logger.info(LOG_SEP)
        logger.info("Updating all data sources")
        logger.info(LOG_SEP)

        results = {}
        updated_sources = []

        for name, provider in self.providers.items():
            logger.info(f"[{name}] Checking for updates...")
            try:
                was_updated = provider.fetch(force=force)
                results[name] = was_updated

                if was_updated:
                    updated_sources.append(name)
                    logger.info(f"✓ {name} updated to version {provider.get_version()}")
                else:
                    logger.info(f"○ {name} already up-to-date")

            except Exception as e:
                logger.error(f"✗ Failed to update {name}: {e}")
                results[name] = False

        # Rebuild database if any sources were updated
        if rebuild and updated_sources:
            logger.info(LOG_SEP)
            logger.info(f"Sources updated: {', '.join(updated_sources)}")
            logger.info("Rebuilding database...")
            logger.info(LOG_SEP)
            self.rebuild_database()
        elif rebuild:
            logger.info("No sources updated, skipping database rebuild")

        return results

    def update_source(self, source_name: str, force: bool = False, rebuild: bool = True) -> bool:
        """Update a single source"""
        if source_name not in self.providers:
            raise ValueError(f"Unknown source: {source_name}")

        provider = self.providers[source_name]
        logger.info(f"Updating {source_name}...")

        try:
            was_updated = provider.fetch(force=force)

            if was_updated:
                logger.info(f"✓ {source_name} updated")
                if rebuild:
                    logger.info("Rebuilding database...")
                    self.rebuild_database()
            else:
                logger.info(f"○ {source_name} already up-to-date")

            return was_updated

        except Exception as e:
            logger.error(f"✗ Failed to update {source_name}: {e}")
            return False

    def rebuild_database(self):
        """Rebuild the database from current sources."""
        from qq.constants import LOCAL_DATA_DIR
        from qq.internal.build_database import build_database
        from qq.sources.source_config import SourceConfig

        logger.info("Rebuilding database from current sources...")
        build_database(self.sources_dir, SourceConfig(), LOCAL_DATA_DIR)
        logger.info("Database rebuilt successfully.")

    def verify_all(self) -> dict[str, bool]:
        """Verify all sources are valid"""
        logger.info("Verifying all sources...")

        results = {}
        for name, provider in self.providers.items():
            is_valid = provider.verify()
            results[name] = is_valid

            status = "✓" if is_valid else "✗"
            logger.info(f"{status} {name}: {'valid' if is_valid else 'invalid'}")

        return results

    def get_status(self) -> dict[str, SourceStatus]:
        """Get status of all sources"""
        return {name: source.get_status() for name, source in self.providers.items()}
