"""Data quality validation for the qwanqwa database."""

import logging
from typing import Any

from qq.constants import LOG_SEP
from qq.data_model import IdType, RelationType
from qq.internal.data_store import DataStore
from qq.internal.entity_resolution import EntityResolver

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates data quality and identifies issues in the built database."""

    def __init__(self, store: DataStore, resolver: EntityResolver):
        self.store = store
        self.resolver = resolver

    def validate_all(self) -> dict[str, Any]:
        """Run all validation checks and log results."""

        logger.info("Running data validation...")

        results = {
            "total_entities": len(self.store._entities),
            "orphaned_entities": self.find_orphaned_entities(),
            "missing_critical_ids": self.find_missing_critical_ids(),
            "duplicate_identifiers": self.find_duplicate_identifiers(),
            "broken_relations": self.find_broken_relations(),
            "data_completeness": self.check_data_completeness(),
        }

        self._report_results(results)
        return results

    def find_orphaned_entities(self) -> list[str]:
        """Find languoids with no identifiers in the resolver."""
        from qq.interface import Languoid

        orphaned = []
        for entity in self.store.all_of_type(Languoid):
            identity = self.resolver.get_identity(entity.id)
            if not identity or len(identity.identifiers) == 0:
                orphaned.append(entity.id)
        return orphaned

    def find_missing_critical_ids(self) -> dict[str, list[str]]:
        """Find entities missing important identifiers (ISO 639-3 or Glottocode) or names."""
        from qq.interface import Languoid

        missing: dict[str, list[str]] = {
            "no_iso_or_glotto": [],
            "no_name": [],
        }

        for entity in self.store.all_of_type(Languoid):
            identity = self.resolver.get_identity(entity.id)

            has_iso = identity and identity.get_identifier(IdType.ISO_639_3)
            has_glotto = identity and identity.get_identifier(IdType.GLOTTOCODE)

            if not (has_iso or has_glotto):
                missing["no_iso_or_glotto"].append(entity.id)

            if not entity.name:
                missing["no_name"].append(entity.id)

        return missing

    def find_duplicate_identifiers(self) -> dict[str, list[tuple[str, list[str]]]]:
        """Find cases where the same identifier value maps to multiple entities."""
        from qq.interface import Languoid

        duplicates: dict[str, list[tuple[str, list[str]]]] = {}

        for id_type in IdType:
            id_to_entities: dict[str, list[str]] = {}

            for entity in self.store.all_of_type(Languoid):
                identity = self.resolver.get_identity(entity.id)
                if identity:
                    value = identity.get_identifier(id_type)
                    if value:
                        id_to_entities.setdefault(value, []).append(entity.id)

            for value, entities in id_to_entities.items():
                if len(entities) > 1:
                    duplicates.setdefault(id_type.value, []).append((value, entities))

        return duplicates

    def find_broken_relations(self) -> list[dict[str, str]]:
        """Find relations that reference non-existent target entities."""
        broken = []

        for entity in self.store._entities.values():
            for rel_type, relations in entity._relations.items():
                for rel in relations:
                    target = self.store.get(rel.target_id)
                    if not target:
                        broken.append(
                            {
                                "source_id": entity.id,
                                "relation_type": rel_type.value,
                                "target_id": rel.target_id,
                                "error": "Target entity not found",
                            }
                        )

        return broken

    def check_only_one_parent(self) -> list[str]:
        """Find languoids with more than one parent (tree violation)."""
        from qq.interface import Languoid

        issues = []
        for entity in self.store.all_of_type(Languoid):
            parents = entity.get_related(RelationType.PARENT_LANGUOID)
            if len(parents) > 1:
                issues.append(entity.id)
        return issues

    def check_data_completeness(self) -> dict[str, float]:
        """Return percentage of languoids that have each type of data."""
        from qq.interface import Languoid

        languoids = self.store.all_of_type(Languoid)
        total = len(languoids)
        if total == 0:
            return {}

        counts = {
            "has_name": 0,
            "has_iso_639_3": 0,
            "has_glottocode": 0,
            "has_bcp_47": 0,
            "has_speaker_count": 0,
            "has_scripts": 0,
            "has_regions": 0,
            "has_parent": 0,
        }

        for entity in languoids:
            if entity.name:
                counts["has_name"] += 1

            identity = self.resolver.get_identity(entity.id)
            if identity:
                if identity.get_identifier(IdType.ISO_639_3):
                    counts["has_iso_639_3"] += 1
                if identity.get_identifier(IdType.GLOTTOCODE):
                    counts["has_glottocode"] += 1
                if identity.get_identifier(IdType.BCP_47):
                    counts["has_bcp_47"] += 1

            if entity.speaker_count:
                counts["has_speaker_count"] += 1
            if entity.scripts:
                counts["has_scripts"] += 1
            if entity.regions:
                counts["has_regions"] += 1
            if entity.parent:
                counts["has_parent"] += 1

        return {key: (count / total) * 100 for key, count in counts.items()}

    def _report_results(self, results: dict) -> None:
        """Log a summary of validation results."""

        # TODO: probably write this to a file, similar to merge conflicts

        logger.info(LOG_SEP)
        logger.info("Validation Results")
        logger.info(LOG_SEP)

        logger.info(f"Total entities: {results['total_entities']}")

        if results["orphaned_entities"]:
            logger.warning(f"Orphaned entities: {len(results['orphaned_entities'])}")
            logger.warning(results["orphaned_entities"])

        missing = results["missing_critical_ids"]
        if missing["no_iso_or_glotto"]:
            logger.warning(f"Entities without ISO/Glottocode: {len(missing['no_iso_or_glotto'])}")
        if missing["no_name"]:
            logger.warning(f"Entities without names: {len(missing['no_name'])}")

        if results["duplicate_identifiers"]:
            logger.error("Duplicate identifiers found!")
            for id_type, dups in results["duplicate_identifiers"].items():
                logger.error(f"  {id_type}: {len(dups)} duplicates")

        if results["broken_relations"]:
            logger.error(f"Broken relations: {len(results['broken_relations'])}")

        logger.info("Data Completeness:")
        for field, percentage in results["data_completeness"].items():
            logger.info(f"  {field}: {percentage:.1f}%")
