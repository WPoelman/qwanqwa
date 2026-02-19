import csv
import logging
import re
from pathlib import Path

from qq.data_model import CanonicalId, DataSource, IdType, LanguoidLevel, NameEntry, RelationType
from qq.importers.base_importer import BaseImporter
from qq.interface import Languoid

logger = logging.getLogger(__name__)


class GlottologImporter(BaseImporter):
    """Import language family data from Glottolog"""

    source = DataSource.GLOTTOLOG

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name_data: dict[CanonicalId, list[NameEntry]] = {}

    @property
    def name_data(self) -> dict[CanonicalId, list[NameEntry]]:
        """Access collected name data keyed by canonical ID."""
        return self._name_data

    def import_data(self, data_path: Path) -> None:
        """Import from Glottolog CSV files"""
        languoids_file = data_path / "languages.csv"
        classification_file = data_path / "classification.nex"

        logger.info(f"Importing from Glottolog: {languoids_file}")

        # First pass: create all languoids
        languoids_data = []
        with open(languoids_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                languoids_data.append(row)
                self._import_languoid_first_pass(row)

        # Parse Newick trees for direct parent-child relations (families and languages).
        # Glottolog's languages.csv only records the root Family_ID, not the direct parent,
        # so we need the Newick file for the full tree.
        newick_parent_of = self._parse_classification_nex(classification_file)
        logger.info(f"Parsed {len(newick_parent_of)} parent-child relations from classification.nex")

        # Second pass: create parent-child relationships
        for row in languoids_data:
            self._import_languoid_second_pass(row, newick_parent_of)

        # Note: Sibling relationships are computed on-the-fly from parent-child relationships
        # See Languoid.siblings property. Storing them would be potentially quadratic...

        self.log_stats()

    def _import_languoid_first_pass(self, row: dict[str, str]) -> None:
        """First pass: create languoid entities"""
        # Note: CSV columns are capitalized (ID, Name, etc.)
        identifiers = {IdType.GLOTTOCODE: row["ID"]}
        if iso_code := row.get("ISO639P3code"):
            identifiers[IdType.ISO_639_3] = iso_code

        languoid = self.get_or_create_languoid(identifiers)

        if name := row.get("Name"):
            languoid.name = name
            self._name_data[languoid.id] = [
                # "en" is a valid BCP-47 code; resolve_locale_codes() in build_database.py
                # converts it to the canonical ID for English before saving.
                NameEntry(name=name, bcp_47_code="en", is_canonical=True)
            ]
        if level := row.get("Level"):
            languoid.level = LanguoidLevel[level.upper()]
        languoid.latitude = self._parse_float(row.get("Latitude"))
        languoid.longitude = self._parse_float(row.get("Longitude"))

    def _import_languoid_second_pass(self, row: dict[str, str], newick_parent_of: dict[str, str]) -> None:
        """Second pass: create parent-child relationships.

        Uses Newick-derived direct parent relations for languages and families.
        Falls back to Language_ID for dialects (dialect -> host language).
        Falls back to Family_ID (root family) only as a last resort.
        """
        glottocode = row["ID"]

        # Determine the direct parent glottocode
        if glottocode in newick_parent_of:
            parent_glottocode = newick_parent_of[glottocode]
        elif language_id := row.get("Language_ID"):
            # Dialect: use the host language as parent
            parent_glottocode = language_id
        elif family_id := row.get("Family_ID"):
            # No direct parent found in Newick (e.g. top-level family member);
            # use root family as fallback.
            parent_glottocode = family_id
        else:
            return  # isolate or root family

        if parent_glottocode == glottocode:
            return  # self-referential (root node appears as its own family)

        child_id = self.resolver.resolve(IdType.GLOTTOCODE, glottocode)
        parent_id = self.resolver.resolve(IdType.GLOTTOCODE, parent_glottocode)

        if not child_id or not parent_id:
            return

        child = self.entity_set.get(child_id)
        parent = self.entity_set.get(parent_id)

        if child and parent and isinstance(child, Languoid) and isinstance(parent, Languoid):
            self.add_bidirectional_relation(child, RelationType.PARENT_LANGUOID, parent, RelationType.CHILD_LANGUOID)

    def _parse_classification_nex(self, path: Path) -> dict[str, str]:
        """Parse Glottolog's classification.nex and return {child_code: parent_code}.

        The file contains one Newick tree per language family, e.g.:
            tree indo1319 = [&R] ((hitt1242:1,...)germ1287:1,...)indo1319:1;
        Branch lengths are always 1 and glottocodes are used as node labels.
        """
        parent_of: dict[str, str] = {}

        tree_re = re.compile(r"tree\s+\S+\s*=\s*\[&R\]\s*(.+);")
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = tree_re.match(line.strip())
                if m:
                    self._parse_newick(m.group(1), parent_of)

        return parent_of

    def _parse_newick(self, newick: str, parent_of: dict[str, str]) -> str | None:
        """Recursively parse a Newick string, populating parent_of in place.

        Returns the root node's glottocode.
        """
        pos = 0

        def parse(pos: int) -> tuple[str | None, int]:
            if pos >= len(newick) or newick[pos] in (",", ")"):
                return None, pos
            if newick[pos] == "(":
                pos += 1  # consume '('
                children: list[str] = []
                while pos < len(newick) and newick[pos] != ")":
                    child, pos = parse(pos)
                    if child is not None:
                        children.append(child)
                    if pos < len(newick) and newick[pos] == ",":
                        pos += 1  # consume ','
                pos += 1  # consume ')'
            else:
                children = []

            # Read node label (glottocode optionally followed by :branchlength)
            label = ""
            while pos < len(newick) and newick[pos] not in (",", ")", ";"):
                label += newick[pos]
                pos += 1
            node = label.split(":")[0]
            for child in children:
                parent_of[child] = node
            return node, pos

        parse(pos)
        return None

    @staticmethod
    def _parse_float(value: str | None) -> float | None:
        """Parse float value safely"""
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
