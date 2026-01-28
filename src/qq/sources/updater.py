import json
import logging
from datetime import datetime
from pathlib import Path

from qq.constants import LOG_SEP
from qq.sources.source_config import SourceConfig

logger = logging.getLogger(__name__)


class SourceUpdater:
    """Manages updating all data sources and rebuilding the database"""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.sources_dir = self.base_dir / "sources"
        self.sources_dir.mkdir(parents=True, exist_ok=True)

        # We don't want the sources in git
        ignore_file = Path(self.sources_dir.parent / ".gitignore")
        if not ignore_file.exists():
            ignore_file.write_text("*")

        self.data_dir = self.base_dir / "data"
        self.providers = {p.name: p for p in SourceConfig.get_providers(self.base_dir)}
        self.update_log_file = self.base_dir / "update_log.json"

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
            logger.info(f"\n[{name}] Checking for updates...")
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

        # Log update
        self._log_update(results, updated_sources)

        # Rebuild database if any sources were updated
        if rebuild and updated_sources:
            logger.info("\n" + LOG_SEP)
            logger.info(f"Sources updated: {', '.join(updated_sources)}")
            logger.info("Rebuilding database...")
            logger.info(LOG_SEP)
            self.rebuild_database()
        elif rebuild:
            logger.info("\nNo sources updated, skipping database rebuild")

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
                self._log_update({source_name: True}, [source_name])

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
        """Rebuild the database from current sources"""
        # TODO: add database builder to updater, next step!!!
        pass

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

    def get_status(self) -> dict[str, dict]:
        """Get status of all sources"""
        status = {}

        for name, provider in self.providers.items():
            status[name] = {
                "version": provider.get_version(),
                "last_updated": provider.metadata._last_updated.isoformat()
                if provider.metadata._last_updated
                else None,
                "last_checked": provider.metadata._last_checked.isoformat()
                if provider.metadata._last_checked
                else None,
                "checksum": provider.metadata._checksum,
                "is_valid": provider.verify(),
                "data_path": str(provider.get_data_path()),
            }

        return status

    def _log_update(self, results: dict[str, bool], updated_sources: list[str]):
        """Log update to file"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "updated_sources": updated_sources,
            "source_versions": {name: provider.get_version() for name, provider in self.providers.items()},
        }

        log = []
        if self.update_log_file.exists():
            log = json.loads(self.update_log_file.read_bytes())
        log.append(log_entry)
        log = log[-100:]  # Only keep last 100
        self.update_log_file.write_text(json.dumps(log, indent=2, ensure_ascii=False))
