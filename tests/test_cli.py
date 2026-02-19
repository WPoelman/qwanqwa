from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from qq.access import Database
from qq.cli import cli
from qq.data_model import IdType
from qq.importers.glotscript_importer import GlotscriptImporter
from qq.importers.glottolog_importer import GlottologImporter
from qq.importers.linguameta_importer import LinguaMetaImporter
from qq.importers.pycountry_importer import PycountryImporter
from qq.importers.sil_importer import SILImporter
from qq.importers.wikipedia_importer import WikipediaImporter
from qq.internal.entity_resolution import EntityResolver
from qq.internal.merge import merge

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def runner():
    """CLI runner that reuses session."""
    return CliRunner()


@pytest.fixture(scope="session")
def access():
    """Build a Database from fixture data (shared across CLI tests)."""
    resolver = EntityResolver()

    importers_config = [
        ("linguameta", LinguaMetaImporter),
        ("glottolog", GlottologImporter),
        ("glotscript", GlotscriptImporter),
        ("pycountry", PycountryImporter),
        ("wikipedia", WikipediaImporter),
        ("sil", SILImporter),
    ]

    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "ron"})
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "knw"})
    resolver.find_or_create_canonical_id({IdType.ISO_639_3: "huc"})

    to_merge = []
    for source_name, importer_class in importers_config:
        imp = importer_class(resolver)
        imp.import_data(FIXTURES / source_name)
        to_merge.append((importer_class.source, imp.entity_set))

    store = merge(to_merge)
    return Database(store, resolver)


class TestCLIBasicCommands:
    """Test basic CLI commands that don't require build dependencies."""

    def test_help(self, runner):
        """Test that --help works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "qwanqwa - Language metadata toolkit" in result.output

    def test_help_lists_all_commands(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        for cmd in ["update", "status", "verify", "rebuild", "get", "search", "validate", "generate-docs"]:
            assert cmd in result.output


class TestCLIBuildCommands:
    """Test CLI commands that require build dependencies."""

    def test_status(self, runner):
        """Test the status command."""
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Data Source Status" in result.output
        assert "linguameta" in result.output
        assert "glottolog" in result.output
        assert "glotscript" in result.output

    def test_verify(self, runner):
        """Test the verify command."""
        result = runner.invoke(cli, ["verify"])
        assert result.exit_code == 0

    def test_update_help(self, runner):
        """Test the update command help."""
        result = runner.invoke(cli, ["update", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output
        assert "--no-rebuild" in result.output
        assert "--source" in result.output

    def test_rebuild(self, runner):
        """Test rebuild delegates to the source updater."""
        mock_updater = MagicMock()
        with patch("qq.cli._get_source_updater", return_value=mock_updater):
            result = runner.invoke(cli, ["rebuild"])
        assert result.exit_code == 0
        mock_updater.rebuild_database.assert_called_once()


class TestCLIGetCommand:
    """Test the `qq get` command."""

    def test_get_by_bcp47(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["get", "nl"])
        assert result.exit_code == 0
        assert "Dutch" in result.output
        assert "BCP-47" in result.output

    def test_get_shows_identifiers(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["get", "nl"])
        assert result.exit_code == 0
        assert "nld" in result.output  # ISO 639-3

    def test_get_with_explicit_type(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["get", "nld", "--type", "ISO_639_3"])
        assert result.exit_code == 0
        assert "Dutch" in result.output

    def test_get_unknown_type(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["get", "nl", "--type", "UNKNOWN_TYPE"])
        assert result.exit_code == 0
        assert "Unknown identifier type" in result.output
        assert "Valid types" in result.output

    def test_get_not_found(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["get", "zzz"])
        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    def test_get_help(self, runner):
        result = runner.invoke(cli, ["get", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output


class TestCLISearchCommand:
    """Test the `qq search` command."""

    def test_search_finds_results(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["search", "Dutch"])
        assert result.exit_code == 0
        assert "Dutch" in result.output
        assert "Found" in result.output

    def test_search_case_insensitive(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["search", "dutch"])
        assert result.exit_code == 0
        assert "Dutch" in result.output

    def test_search_no_results(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["search", "nope-buddy"])
        assert result.exit_code == 0
        assert "No results" in result.output

    def test_search_help(self, runner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0


class TestCLIValidateCommand:
    """Test the `qq validate` command."""

    def test_validate_shows_statistics(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 0
        assert "Database Statistics" in result.output
        assert "Total languoids" in result.output
        assert "Total scripts" in result.output
        assert "Total regions" in result.output

    def test_validate_shows_completeness(self, runner, access):
        with patch("qq.cli._get_access", return_value=access):
            result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 0
        assert "Data Completeness" in result.output
        assert "has_name" in result.output

    def test_validate_help(self, runner):
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
