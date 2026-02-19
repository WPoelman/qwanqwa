from unittest.mock import Mock, patch

import pytest

from qq.sources.providers import DirectorySourceProvider, SourceMetadata, SourceType
from qq.sources.updater import SourceUpdater


@pytest.fixture
def temp_base_dir(tmp_path):
    """Create temporary base directory structure"""
    base_dir = tmp_path / "qq_test"
    base_dir.mkdir()
    (base_dir / "sources").mkdir()
    return base_dir


@pytest.fixture
def mock_providers(temp_base_dir):
    """Create mock providers for testing"""
    providers = []

    for name in ["linguameta", "glottolog", "glotscript", "pycountry", "wikipedia"]:
        provider = Mock(spec=DirectorySourceProvider)
        provider.name = name
        provider.metadata = SourceMetadata(
            name=name, license="CC", source_type=SourceType.GIT, source_url=f"https://example.com/{name}"
        )
        provider.get_version.return_value = "1.0.0"
        provider.verify.return_value = True

        data_path = temp_base_dir / "sources" / name
        data_path.mkdir(parents=True, exist_ok=True)
        provider.data_dir = data_path

        providers.append(provider)

    return providers


class TestSourceUpdater:
    """Tests for SourceUpdater"""

    def test_init(self, temp_base_dir):
        """Test initializing the updater"""
        updater = SourceUpdater(temp_base_dir)

        assert updater.sources_dir == temp_base_dir
        assert isinstance(updater.providers, dict)

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_all_success(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test updating all sources successfully"""
        mock_get_providers.return_value = mock_providers

        for provider in mock_providers:
            provider.fetch.return_value = True

        updater = SourceUpdater(temp_base_dir)
        results = updater.update_all(rebuild=False)

        assert len(results) == 5
        assert all(results.values())

        for provider in mock_providers:
            provider.fetch.assert_called_once_with(force=False)

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_all_no_updates(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test when no sources need updates"""
        mock_get_providers.return_value = mock_providers

        for provider in mock_providers:
            provider.fetch.return_value = False

        updater = SourceUpdater(temp_base_dir)
        results = updater.update_all(rebuild=False)

        assert len(results) == 5
        assert not any(results.values())

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_all_with_force(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test forcing updates on all sources"""
        mock_get_providers.return_value = mock_providers

        for provider in mock_providers:
            provider.fetch.return_value = True

        updater = SourceUpdater(temp_base_dir)
        updater.update_all(force=True, rebuild=False)

        for provider in mock_providers:
            provider.fetch.assert_called_once_with(force=True)

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_all_with_rebuild(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test updating all sources and rebuilding database"""
        mock_get_providers.return_value = mock_providers

        for provider in mock_providers:
            provider.fetch.return_value = True

        updater = SourceUpdater(temp_base_dir)

        with patch.object(updater, "rebuild_database") as mock_rebuild:
            updater.update_all(rebuild=True)
            mock_rebuild.assert_called_once()

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_all_skip_rebuild_when_no_updates(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test skipping rebuild when no sources were updated"""
        mock_get_providers.return_value = mock_providers

        for provider in mock_providers:
            provider.fetch.return_value = False

        updater = SourceUpdater(temp_base_dir)

        with patch.object(updater, "rebuild_database") as mock_rebuild:
            updater.update_all(rebuild=True)
            mock_rebuild.assert_not_called()

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_source_success(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test updating a single source successfully"""
        mock_get_providers.return_value = mock_providers
        mock_providers[1].fetch.return_value = True

        updater = SourceUpdater(temp_base_dir)

        with patch.object(updater, "rebuild_database") as mock_rebuild:
            result = updater.update_source("glottolog", rebuild=True)

            assert result is True
            mock_providers[1].fetch.assert_called_once_with(force=False)
            mock_rebuild.assert_called_once()

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_source_no_update(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test when single source doesn't need update"""
        mock_get_providers.return_value = mock_providers
        mock_providers[1].fetch.return_value = False

        updater = SourceUpdater(temp_base_dir)

        with patch.object(updater, "rebuild_database") as mock_rebuild:
            result = updater.update_source("glottolog", rebuild=True)

            assert result is False
            mock_rebuild.assert_not_called()

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_source_unknown(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test updating an unknown source"""
        mock_get_providers.return_value = mock_providers

        updater = SourceUpdater(temp_base_dir)

        with pytest.raises(ValueError, match="Unknown source"):
            updater.update_source("unknown_source")

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_source_with_force(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test forcing update on a single source"""
        mock_get_providers.return_value = mock_providers
        mock_providers[1].fetch.return_value = True

        updater = SourceUpdater(temp_base_dir)

        with patch.object(updater, "rebuild_database"):
            updater.update_source("glottolog", force=True, rebuild=False)
            mock_providers[1].fetch.assert_called_once_with(force=True)

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_update_source_handles_error(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test handling errors when updating single source"""
        mock_get_providers.return_value = mock_providers
        mock_providers[1].fetch.side_effect = Exception("Update failed")

        updater = SourceUpdater(temp_base_dir)
        result = updater.update_source("glottolog", rebuild=False)

        assert result is False

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_verify_all_success(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test verifying all sources successfully"""
        mock_get_providers.return_value = mock_providers

        for provider in mock_providers:
            provider.verify.return_value = True

        updater = SourceUpdater(temp_base_dir)
        results = updater.verify_all()

        assert len(results) == 5
        assert all(results.values())


class TestSourceUpdaterIntegration:
    """Integration tests for SourceUpdater with real providers"""

    @patch("qq.sources.source_config.SourceConfig.get_providers")
    def test_full_update_workflow(self, mock_get_providers, temp_base_dir, mock_providers):
        """Test complete update workflow"""
        mock_get_providers.return_value = mock_providers

        mock_providers[0].fetch.return_value = True
        mock_providers[1].fetch.return_value = False
        mock_providers[2].fetch.return_value = True
        mock_providers[3].fetch.return_value = False
        mock_providers[4].fetch.return_value = False

        for provider in mock_providers:
            provider.verify.return_value = True

        updater = SourceUpdater(temp_base_dir)

        with patch.object(updater, "rebuild_database") as mock_rebuild:
            results = list(updater.update_all(rebuild=True).values())

            assert results[0] is True
            assert results[1] is False
            assert results[2] is True

            mock_rebuild.assert_called_once()

        verify_results = updater.verify_all()
        assert all(verify_results.values())

        status = updater.get_status()
        assert len(status) == 5
