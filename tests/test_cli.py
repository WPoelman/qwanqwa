import pytest
from click.testing import CliRunner

from qq.cli import cli


@pytest.fixture(scope="session")
def runner():
    """CLI runner that reuses session."""
    _runner = CliRunner()

    class InjectingRunner:
        def invoke(self, *args, **kwargs):
            kwargs.setdefault("obj")  # TODO inject language data here once implemented
            return _runner.invoke(*args, **kwargs)

    return InjectingRunner()


class TestCLIBasicCommands:
    """Test basic CLI commands that don't require build dependencies."""

    def test_help(self, runner):
        """Test that --help works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "qwanqwa - Language metadata toolkit" in result.output


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
