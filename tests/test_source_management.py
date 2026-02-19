from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from qq.sources.providers import DirectorySourceProvider, GitSourceProvider, SourceType


@pytest.fixture
def temp_sources_dir(tmp_path):
    """Create a temporary sources directory"""
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    return sources_dir


@pytest.fixture
def git_provider(temp_sources_dir):
    provider = GitSourceProvider(
        name="test_repo",
        license="CC",
        sources_dir=temp_sources_dir,
        source_url="https://github.com/test/repo.git",
        branch="main",
    )
    return provider


class TestGitSourceProvider:
    """Tests for GitSourceProvider"""

    def test_init(self, temp_sources_dir):
        """Test initializing a Git source provider"""
        provider = GitSourceProvider(
            name="test_repo",
            sources_dir=temp_sources_dir,
            source_url="https://github.com/test/repo.git",
            branch="main",
            license="MIT",
        )
        assert provider.name == "test_repo"
        assert provider.source_url == "https://github.com/test/repo.git"
        assert provider.branch == "main"
        assert provider.metadata.source_type == SourceType.GIT
        assert provider.repo_path == temp_sources_dir / "test_repo_repo"

    @patch("subprocess.run")
    def test_fetch_clone_new_repo(self, mock_run, temp_sources_dir, git_provider):
        """Test cloning a new repository"""

        def create_repo_side_effect(*args, **kwargs):
            repo_path = temp_sources_dir / "test_repo_repo"
            repo_path.mkdir(parents=True, exist_ok=True)
            (repo_path / "test.txt").write_text("test")
            if "rev-parse" in args[0]:
                return Mock(stdout="abcd1234\n", returncode=0)
            return Mock(returncode=0)

        mock_run.side_effect = create_repo_side_effect

        result = git_provider.fetch()

        assert result is True
        assert mock_run.call_count >= 1
        clone_call = mock_run.call_args_list[0]
        assert "git" in clone_call[0][0]
        assert "clone" in clone_call[0][0]

    @patch("subprocess.run")
    def test_fetch_update_existing_repo(self, mock_run, temp_sources_dir, git_provider):
        """Test updating an existing repository"""
        repo_path = temp_sources_dir / "test_repo_repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()
        (repo_path / "test.txt").write_text("test")

        def side_effect_func(*args, **kwargs):
            if "rev-parse" in args[0]:
                if not hasattr(side_effect_func, "call_count"):
                    side_effect_func.call_count = 0  # type: ignore
                side_effect_func.call_count += 1  # type: ignore
                if side_effect_func.call_count == 1:  # type: ignore
                    return Mock(stdout="old_commit_hash\n", returncode=0)
                else:
                    return Mock(stdout="new_commit_hash\n", returncode=0)
            return Mock(returncode=0)

        mock_run.side_effect = side_effect_func

        result = git_provider.fetch()

        assert result is True
        assert mock_run.call_count == 4

    @patch("subprocess.run")
    def test_fetch_no_update_needed(self, mock_run, temp_sources_dir, git_provider):
        """Test when repository is already up-to-date"""

        repo_path = temp_sources_dir / "test_repo_repo"
        repo_path.mkdir(parents=True)
        (repo_path / ".git").mkdir()
        (repo_path / "test.txt").write_text("test")

        same_hash = "same_commit_hash\n"

        def side_effect_func(*args, **kwargs):
            return Mock(stdout=same_hash, returncode=0)

        mock_run.side_effect = side_effect_func

        result = git_provider.fetch()

        assert result is False

    @patch("subprocess.run")
    def test_get_version(self, mock_run, temp_sources_dir, git_provider):
        """Test getting current git version"""

        repo_path = temp_sources_dir / "test_repo_repo"
        repo_path.mkdir(parents=True)

        mock_run.return_value = Mock(stdout="abcdef1234567890\n", returncode=0)

        version = git_provider.get_version()

        assert version == "abcdef12"

    @patch("subprocess.run")
    def test_verify_valid_repo(self, mock_run, temp_sources_dir, git_provider):
        """Test verifying a valid repository"""
        repo_path = temp_sources_dir / "test_repo_repo"
        repo_path.mkdir(parents=True)

        mock_run.return_value = Mock(returncode=0)

        assert git_provider.verify() is True

    def test_verify_missing_repo(self, temp_sources_dir, git_provider):
        """Test verifying a missing repository"""

        assert git_provider.verify() is False


class TestDirectorySourceProvider:
    """Tests for DirectorySourceProvider"""

    def test_init(self, temp_sources_dir, tmp_path):
        """Test initializing a directory source provider"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )
        assert provider.name == "local_source"
        assert provider.local_path == local_dir
        assert provider.metadata.source_type == SourceType.DIR

    def test_fetch_new_data(self, temp_sources_dir, tmp_path):
        """Test fetching data from a local directory"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()
        (local_dir / "test.txt").write_text("test data")

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        result = provider.fetch()

        assert result is True
        target_path = provider.data_dir
        assert target_path.exists()
        assert (target_path / "test.txt").read_text() == "test data"

    def test_fetch_no_update_needed(self, temp_sources_dir, tmp_path):
        """Test when local data hasn't changed"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()
        (local_dir / "test.txt").write_text("test data")

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        provider.fetch()
        result = provider.fetch(force=False)

        assert result is False

    def test_fetch_with_force(self, temp_sources_dir, tmp_path):
        """Test forcing a fetch even when data hasn't changed"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()
        (local_dir / "test.txt").write_text("test data")

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        provider.fetch()
        result = provider.fetch(force=True)

        assert result is True

    def test_fetch_missing_local_path(self, temp_sources_dir, tmp_path):
        """Test fetching when local path doesn't exist"""
        local_dir = tmp_path / "nonexistent"

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        with pytest.raises(FileNotFoundError):
            provider.fetch()

    def test_get_version(self, temp_sources_dir, tmp_path):
        """Test getting version (checksum)"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()
        (local_dir / "test.txt").write_text("test data")

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        provider.fetch()
        version = provider.get_version()

        assert version is not None
        assert len(version) == 8

    def test_verify_valid_path(self, temp_sources_dir, tmp_path):
        """Test verifying a valid local path"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        assert provider.verify() is True

    def test_verify_missing_path(self, temp_sources_dir, tmp_path):
        """Test verifying a missing local path"""
        local_dir = tmp_path / "nonexistent"

        provider = DirectorySourceProvider(
            name="local_source", sources_dir=temp_sources_dir, local_path=local_dir, license="CC0"
        )

        assert provider.verify() is False


class TestSourceProviderMetadata:
    """Tests for metadata save/load functionality"""

    def test_save_and_load_metadata(self, temp_sources_dir, tmp_path):
        """Test saving and loading metadata"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()

        provider = DirectorySourceProvider(
            name="test_source", sources_dir=temp_sources_dir, local_path=local_dir, license="MIT"
        )

        provider.metadata._version = "1.0.0"
        provider.metadata._last_updated = datetime(2024, 1, 1, 12, 0, 0)
        provider.metadata._checksum = "abc123"
        provider._save_metadata()

        provider2 = DirectorySourceProvider(
            name="test_source", sources_dir=temp_sources_dir, local_path=local_dir, license="MIT"
        )

        assert provider2.metadata._version == "1.0.0"
        assert provider2.metadata._last_updated == datetime(2024, 1, 1, 12, 0, 0)
        assert provider2.metadata._checksum == "abc123"

    def test_file_checksum(self, temp_sources_dir, tmp_path):
        """Test calculating file checksum"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()
        test_file = local_dir / "test.txt"
        test_file.write_text("test content")

        provider = DirectorySourceProvider(
            name="test_source", sources_dir=temp_sources_dir, local_path=local_dir, license="MIT"
        )

        checksum = provider._file_checksum(test_file)
        assert isinstance(checksum, str)
        assert len(checksum) == 64

        checksum2 = provider._file_checksum(test_file)
        assert checksum == checksum2

    def test_dir_checksum(self, temp_sources_dir, tmp_path):
        """Test calculating directory checksum"""
        local_dir = tmp_path / "local_data"
        local_dir.mkdir()
        (local_dir / "file1.txt").write_text("content 1")
        (local_dir / "file2.txt").write_text("content 2")

        provider = DirectorySourceProvider(
            name="test_source", sources_dir=temp_sources_dir, local_path=local_dir, license="MIT"
        )

        checksum = provider._dir_checksum(local_dir)
        assert isinstance(checksum, str)
        assert len(checksum) == 64

        checksum2 = provider._dir_checksum(local_dir)
        assert checksum == checksum2


class TestFileDownloadSourceProvider:
    # TODO: add testing for file download
    pass
