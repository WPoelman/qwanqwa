import logging
from dataclasses import dataclass, field
from typing import Any

from qq.data_model import CanonicalId, IdType

logger = logging.getLogger(__name__)

__all__ = [
    "EntityIdentity",
    "EntityResolver",
]


@dataclass
class EntityIdentity:
    """Tracks all known identifiers for a single entity."""

    canonical_id: CanonicalId  # internal: "lang:00001" or "script:0001"
    identifiers: dict[IdType, str] = field(default_factory=dict)

    def add_identifier(self, id_type: IdType, value: str):
        """Add a new identifier for this entity"""
        if id_type in self.identifiers and self.identifiers[id_type] != value:
            logger.warning(
                f"Identifier conflict for {self.canonical_id}: "
                f"{id_type.value} was {self.identifiers[id_type]}, now {value}"
            )

        self.identifiers[id_type] = value

    def get_identifier(self, id_type: IdType) -> str | None:
        """Get identifier of a specific type"""
        return self.identifiers.get(id_type)

    def has_identifier(self, id_type: IdType, value: str) -> bool:
        """Check if entity has a specific identifier"""
        return self.identifiers.get(id_type) == value

    def __repr__(self):
        ids = ", ".join(f"{k.value}={v}" for k, v in self.identifiers.items())
        return f"EntityIdentity({self.canonical_id}: {ids})"


class EntityResolver:
    """Resolves different identifiers to canonical entity IDs."""

    def __init__(self):
        # Map from (IdType, value) -> canonical_id
        self._id_to_canonical: dict[tuple, CanonicalId] = {}

        # Map from canonical_id -> EntityIdentity
        self._identities: dict[CanonicalId, EntityIdentity] = {}

        # Counter for generating new canonical IDs
        self._next_id = 1

        # Deprecated/retired code tracking: (IdType, value) -> reason string
        self._deprecated_codes: dict[tuple[IdType, str], str] = {}

    def register_entity(self, identity: EntityIdentity) -> CanonicalId:
        """Register a new entity identity. Returns the canonical ID."""
        canonical_id = identity.canonical_id

        self._identities[canonical_id] = identity

        # Index all identifiers
        for id_type, value in identity.identifiers.items():
            key = (id_type, value)
            if key in self._id_to_canonical:
                existing_id = self._id_to_canonical[key]
                if existing_id != canonical_id:
                    logger.warning(
                        f"Identifier collision: {id_type.value}={value} maps to both {existing_id} and {canonical_id}"
                    )
            self._id_to_canonical[key] = canonical_id

        return canonical_id

    def resolve(self, id_type: IdType, value: str) -> CanonicalId | None:
        """Resolve an identifier to a canonical entity ID, returns None if not found.

        ISO 639-2T codes are identical to ISO 639-3 codes, so ISO_639_2T lookups
        are handled by ISO_639_3 codes.
        """
        if id_type == IdType.ISO_639_2T:
            return self._id_to_canonical.get((IdType.ISO_639_3, value))
        return self._id_to_canonical.get((id_type, value))

    def find(self, id_type: IdType, value: str) -> EntityIdentity | None:
        """Tries to find the full identity, returns None if not found."""
        if canonical_id := self.resolve(id_type, value):
            return self.get_identity(canonical_id)
        else:
            return None

    def find_or_create_canonical_id(self, identifiers: dict[IdType, str]) -> CanonicalId:
        """
        Find existing entity with any of these identifiers or create a new canonical ID.
        """
        # Try to find existing entity by any identifier
        candidate_ids = set()
        for id_type, value in identifiers.items():
            canonical_id = self.resolve(id_type, value)
            if canonical_id:
                candidate_ids.add(canonical_id)

        if len(candidate_ids) == 0:
            # No existing entity found - create new one
            canonical_id = self._generate_canonical_id()
            identity = EntityIdentity(canonical_id)

            for id_type, value in identifiers.items():
                identity.add_identifier(id_type, value)

            self.register_entity(identity)
            logger.debug(f"Created new entity: {canonical_id}")
            return canonical_id

        elif len(candidate_ids) == 1:
            # Found existing entity - update with new identifiers
            canonical_id = candidate_ids.pop()
            identity = self._identities[canonical_id]

            for id_type, value in identifiers.items():
                if id_type not in identity.identifiers:
                    identity.add_identifier(id_type, value)
                    # Update index
                    self._id_to_canonical[(id_type, value)] = canonical_id

            logger.debug(f"Updated entity: {canonical_id}")
            return canonical_id

        else:
            # Multiple candidates - need to merge entities!
            logger.warning(
                f"Multiple entities found for identifiers {identifiers}: {candidate_ids}. Merging into first one."
            )
            return self._merge_entities(candidate_ids, identifiers)

    def _merge_entities(self, canonical_ids: set[CanonicalId], new_identifiers: dict[IdType, str]) -> CanonicalId:
        """
        Merge multiple entities that were discovered to be the same.
        This happens when different sources link the same real-world entity.
        """
        # Use the first ID as the primary one
        primary_id = sorted(canonical_ids)[0]
        primary_identity = self._identities[primary_id]

        # Merge all identifiers from other entities
        for other_id in canonical_ids:
            if other_id == primary_id:
                continue

            other_identity = self._identities[other_id]

            # Copy all identifiers to primary
            for id_type, value in other_identity.identifiers.items():
                if id_type not in primary_identity.identifiers:
                    primary_identity.add_identifier(id_type, value)
                # Update index to point to primary (even if already exists)
                self._id_to_canonical[(id_type, value)] = primary_id

            # Remove the merged entity
            del self._identities[other_id]

        # Add new identifiers
        for id_type, value in new_identifiers.items():
            if id_type not in primary_identity.identifiers:
                primary_identity.add_identifier(id_type, value)
                self._id_to_canonical[(id_type, value)] = primary_id

        return primary_id

    def get_identity(self, canonical_id: CanonicalId) -> EntityIdentity | None:
        """Get the full identity for a canonical ID, returns None if not found"""
        return self._identities.get(canonical_id)

    def get_all_identifiers(self, canonical_id: CanonicalId) -> dict[IdType, str] | None:
        """Get all identifiers for an entity, returns None if not found"""
        identity = self.get_identity(canonical_id)
        return identity.identifiers if identity else None

    def _generate_canonical_id(self) -> CanonicalId:
        """Generate a new unique canonical ID"""
        canonical_id = f"lang:{self._next_id:06d}"
        self._next_id += 1
        return canonical_id

    def register_alias(self, id_type: IdType, value: str, canonical_id: CanonicalId) -> None:
        """Register an additional identifier for an existing entity."""
        self._id_to_canonical[(id_type, value)] = canonical_id

    def register_deprecated(self, id_type: IdType, value: str, reason: str) -> None:
        """Mark a code as deprecated/retired."""
        self._deprecated_codes[(id_type, value)] = reason

    def is_deprecated(self, id_type: IdType, value: str) -> bool:
        """Check if a code is deprecated/retired."""
        return (id_type, value) in self._deprecated_codes

    def stats(self) -> dict[str, Any]:
        """Get summary statistics about entity resolution."""
        identifier_counts = [len(identity.identifiers) for identity in self._identities.values()]
        return {
            "total_entities": len(self._identities),
            "total_identifier_mappings": len(self._id_to_canonical),
            "max_identifiers_per_entity": max(identifier_counts) if identifier_counts else 0,
            "min_identifiers_per_entity": min(identifier_counts) if identifier_counts else 0,
        }
