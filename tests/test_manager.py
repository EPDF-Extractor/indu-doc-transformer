"""
Tests for the Manager module.

This module tests the Manager class and its methods for coordinating
document processing plugins.
"""

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock

from indu_doc.manager import Manager
from indu_doc.configs import AspectsConfig
from indu_doc.plugins.plugin import InduDocPlugin
from indu_doc.plugins.events import EventType, ProcessingCompletedEvent
from indu_doc.god import God


class TestManager:
    """Test Manager class functionality."""

    @pytest.fixture
    def mock_configs(self):
        """Create mock AspectsConfig."""
        configs = MagicMock(spec=AspectsConfig)
        configs.separators = ["=", "+"]
        return configs

    @pytest.fixture
    def manager(self, mock_configs):
        """Create Manager instance."""
        return Manager(mock_configs)

    @pytest.fixture
    def mock_wait_for(self):
        """Mock for asyncio.wait_for."""
        with patch('asyncio.wait_for') as mock:
            yield mock

    @pytest.fixture
    def mock_gather(self):
        """Mock for asyncio.gather."""
        with patch('asyncio.gather') as mock:
            yield mock

    def test_init(self, mock_configs):
        """Test Manager initialization."""
        manager = Manager(mock_configs)
        assert manager.configs == mock_configs
        assert isinstance(manager.god, God)
        assert manager.plugins == []
        assert manager._file_progress == {}

    def test_from_config_files(self):
        """Test creating Manager from config files."""
        config_data = {"aspects": [{"Aspect": "Test", "Separator": "="}]}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(config_data, f)
            config_path = f.name

        try:
            with patch('indu_doc.configs.AspectsConfig.init_from_file') as mock_init:
                mock_configs = MagicMock()
                mock_init.return_value = mock_configs

                manager = Manager.from_config_files(config_path)
                assert isinstance(manager, Manager)
                assert manager.configs == mock_configs
                mock_init.assert_called_once_with(config_path)
        finally:
            os.unlink(config_path)

    def test_register_plugin(self, manager):
        """Test plugin registration."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.event_emitter = MagicMock()

        manager.register_plugin(mock_plugin)

        assert mock_plugin in manager.plugins
        mock_plugin.event_emitter.on.assert_any_call(EventType.PROCESSING_COMPLETED, manager._on_plugin_event)
        mock_plugin.event_emitter.on.assert_any_call(EventType.PROCESSING_ERROR, manager._on_plugin_event)
        mock_plugin.event_emitter.on.assert_any_call(EventType.PROCESSING_STOPPED, manager._on_plugin_event)
        mock_plugin.event_emitter.on.assert_any_call(EventType.PROCESSING_PROGRESS, manager._on_plugin_event)

    def test_distribute_files_to_plugins(self, manager):
        """Test file distribution to plugins."""
        # Create mock plugins with different supported extensions
        plugin1 = MagicMock(spec=InduDocPlugin)
        plugin1.get_supported_file_extensions.return_value = ("pdf",)
        plugin2 = MagicMock(spec=InduDocPlugin)
        plugin2.get_supported_file_extensions.return_value = ("docx",)

        manager.plugins = [plugin1, plugin2]

        file_paths = ("test.pdf", "test.docx", "test.txt")
        distribution = manager._distribute_files_to_plugins(file_paths)

        assert plugin1 in distribution
        assert plugin2 in distribution
        assert distribution[plugin1] == ("test.pdf",)
        assert distribution[plugin2] == ("test.docx",)

    @patch('os.path.exists', return_value=True)
    @pytest.mark.asyncio
    async def test_process_files_async_success(self, mock_exists, manager):
        """Test successful async file processing."""
        # Setup mock plugin
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.start = AsyncMock()
        manager.plugins = [mock_plugin]

        # Mock file distribution
        with patch.object(manager, '_distribute_files_to_plugins') as mock_distribute:
            mock_distribute.return_value = {mock_plugin: ("test.pdf",)}

            await manager.process_files_async("test.pdf")

            # Verify _distribute_files_to_plugins was called with absolute path
            mock_distribute.assert_called_once()
            args = mock_distribute.call_args[0]
            assert len(args) == 1
            assert args[0][0].endswith("test.pdf")
            mock_plugin.start.assert_called_once_with(("test.pdf",))

    def test_process_files_sync(self, manager):
        """Test synchronous file processing."""
        with patch('asyncio.run') as mock_run:
            with patch.object(manager, 'wait_for_completion') as mock_wait:
                manager.process_files("test.pdf", blocking=True)

                mock_run.assert_called_once()
                mock_wait.assert_called_once()

    def test_process_files_non_blocking(self, manager):
        """Test non-blocking file processing."""
        with patch('asyncio.run') as mock_run:
            with patch.object(manager, 'wait_for_completion') as mock_wait:
                manager.process_files("test.pdf", blocking=False)

                mock_run.assert_called_once()
                mock_wait.assert_not_called()

    def test_process_files_missing_files(self, manager):
        """Test processing with missing files raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="The following files do not exist"):
            manager.process_files("nonexistent.pdf")

    @pytest.mark.asyncio
    async def test_wait_for_completion_async_success(self, mock_wait_for, manager):
        """Test successful async wait for completion."""
        mock_wait_for.return_value = True

        result = await manager.wait_for_completion_async()
        assert result is True
        mock_wait_for.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_completion_async_timeout(self, mock_wait_for, manager):
        """Test async wait for completion with timeout."""
        from asyncio import TimeoutError
        mock_wait_for.side_effect = TimeoutError

        result = await manager.wait_for_completion_async(timeout=5.0)
        assert result is False

    def test_wait_for_completion_sync(self, manager):
        """Test synchronous wait for completion."""
        with patch('asyncio.run') as mock_run:
            mock_run.return_value = True
            result = manager.wait_for_completion()
            assert result is True
            mock_run.assert_called_once()

    def test_get_active_plugins(self, manager):
        """Test getting active plugins."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        manager._Manager__active_plugins.add(mock_plugin)

        active = manager.get_active_plugins()
        assert mock_plugin in active

    def test_has_errors_no_errors(self, manager):
        """Test has_errors when no errors."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.get_state_progress.return_value = {"state": "idle"}
        manager.plugins = [mock_plugin]

        assert not manager.has_errors()

    def test_has_errors_with_errors(self, manager):
        """Test has_errors when there are errors."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.get_state_progress.return_value = {"state": "error"}
        manager.plugins = [mock_plugin]

        assert manager.has_errors()

    def test_get_processing_state(self, manager):
        """Test getting processing state."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.get_state_progress.return_value = {"state": "processing"}
        manager.plugins = [mock_plugin]

        states = manager.get_processing_state()
        assert len(states) == 1
        assert states[0]["state"] == "processing"

    def test_get_file_progress(self, manager):
        """Test getting file progress."""
        manager._file_progress = {"test.pdf": 50.0}
        progress = manager.get_file_progress()
        assert progress["test.pdf"] == 50.0

    def test_is_processing_no_plugins(self, manager):
        """Test is_processing with no plugins."""
        assert not manager.is_processing()

    def test_is_processing_idle_plugins(self, manager):
        """Test is_processing with idle plugins."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin._processing_state = MagicMock()
        mock_plugin._processing_state.value = "idle"
        manager.plugins = [mock_plugin]

        assert not manager.is_processing()

    def test_is_processing_active_plugins(self, manager):
        """Test is_processing with active plugins."""
        from indu_doc.plugins.plugins_common import ProcessingState
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin._processing_state = ProcessingState.PROCESSING
        manager.plugins = [mock_plugin]

        assert manager.is_processing()

    @pytest.mark.asyncio
    async def test_stop_processing_async(self, manager):
        """Test async stop processing."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.stop = AsyncMock()
        manager.plugins = [mock_plugin]

        await manager.stop_processing_async()
        mock_plugin.stop.assert_called_once()

    def test_stop_processing_sync(self, manager):
        """Test synchronous stop processing."""
        with patch('asyncio.run') as mock_run:
            manager.stop_processing()
            mock_run.assert_called_once()

    def test_update_configs_success(self, manager, mock_configs):
        """Test successful config update."""
        new_configs = MagicMock(spec=AspectsConfig)
        new_configs.__ne__ = MagicMock(return_value=True)

        with patch.object(manager, 'is_processing', return_value=False):
            manager.update_configs(new_configs)
            assert manager.configs == new_configs

    def test_update_configs_while_processing(self, manager):
        """Test config update fails while processing."""
        with patch.object(manager, 'is_processing', return_value=True):
            with pytest.raises(RuntimeError, match="Cannot update configs while processing"):
                manager.update_configs(MagicMock())

    def test_get_stats(self, manager):
        """Test getting statistics."""
        # Mock some data in god
        manager.god.xtargets = {"id1": MagicMock(), "id2": MagicMock()}
        manager.god.connections = {"conn1": MagicMock()}
        manager.god.attributes = {"attr1": MagicMock()}
        manager.god.links = {"link1": MagicMock()}
        manager.god.pins = {"pin1": MagicMock()}
        manager.god.aspects = {"asp1": MagicMock()}

        # Mock plugin states
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.get_state_progress.return_value = {"state": "idle"}
        manager.plugins = [mock_plugin]

        stats = manager.get_stats()

        assert stats["num_xtargets"] == 2
        assert stats["num_connections"] == 1
        assert stats["num_attributes"] == 1
        assert stats["num_links"] == 1
        assert stats["num_pins"] == 1
        assert stats["num_aspects"] == 1
        assert "processing_states" in stats

    def test_get_xtargets(self, manager):
        """Test getting xtargets."""
        mock_target = MagicMock()
        manager.god.xtargets = {"id1": mock_target}

        targets = manager.get_xtargets()
        assert mock_target in targets

    def test_get_connections(self, manager):
        """Test getting connections."""
        mock_conn = MagicMock()
        manager.god.connections = {"id1": mock_conn}

        connections = manager.get_connections()
        assert mock_conn in connections

    def test_get_attributes(self, manager):
        """Test getting attributes."""
        mock_attr = MagicMock()
        manager.god.attributes = {"id1": mock_attr}

        attributes = manager.get_attributes()
        assert mock_attr in attributes

    def test_get_links(self, manager):
        """Test getting links."""
        mock_link = MagicMock()
        manager.god.links = {"id1": mock_link}

        links = manager.get_links()
        assert mock_link in links

    def test_get_pins(self, manager):
        """Test getting pins."""
        mock_pin = MagicMock()
        manager.god.pins = {"id1": mock_pin}

        pins = manager.get_pins()
        assert mock_pin in pins

    def test_get_target_pages_by_tag_found(self, manager):
        """Test getting target pages by tag when found."""
        mock_target = MagicMock()
        mock_target.tag.tag_str = "test_tag"
        manager.god.xtargets = {"id1": mock_target}

        with patch.object(manager.god, 'get_pages_of_object') as mock_get_pages:
            mock_get_pages.return_value = {"page1", "page2"}

            result = manager.get_target_pages_by_tag("test_tag")
            assert result["target"] == mock_target
            assert result["pages"] == {"page1", "page2"}

    def test_get_target_pages_by_tag_not_found(self, manager):
        """Test getting target pages by tag when not found."""
        result = manager.get_target_pages_by_tag("nonexistent")
        assert result is None

    def test_get_connection_details_found(self, manager):
        """Test getting connection details when found."""
        mock_conn = MagicMock()
        manager.god.connections = {"guid1": mock_conn}

        with patch.object(manager.god, 'get_pages_of_object') as mock_get_pages:
            mock_get_pages.return_value = {"page1"}

            result = manager.get_connection_details("guid1")
            assert result["connection"] == mock_conn
            assert result["pages"] == {"page1"}

    def test_get_connection_details_not_found(self, manager):
        """Test getting connection details when not found."""
        result = manager.get_connection_details("nonexistent")
        assert result is None

    def test_get_pages_of_object(self, manager):
        """Test getting pages of object."""
        with patch.object(manager.god, 'get_pages_of_object') as mock_get_pages:
            mock_get_pages.return_value = {"page1"}
            result = manager.get_pages_of_object("obj_id")
            assert result == {"page1"}

    def test_get_objects_on_page(self, manager):
        """Test getting objects on page."""
        mock_objects = [MagicMock(), MagicMock()]
        with patch.object(manager.god, 'get_objects_on_page') as mock_get_objects:
            mock_get_objects.return_value = mock_objects
            result = manager.get_objects_on_page(1, "test.pdf")
            assert result == mock_objects

    def test_has_data_true(self, manager):
        """Test has_data when data exists."""
        manager.god.xtargets = {"id1": MagicMock()}
        assert manager.has_data is True

    def test_has_data_false(self, manager):
        """Test has_data when no data exists."""
        assert manager.has_data is False

    @pytest.mark.asyncio
    async def test_on_plugin_event_completed(self, manager):
        """Test handling plugin completed event."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_plugin.sub_god = MagicMock()  # Mock sub_god attribute
        mock_event = ProcessingCompletedEvent("test", mock_plugin, ("file.pdf",), MagicMock())

        # Mock the manager's god to avoid configuration conflicts
        with patch.object(manager, 'god', MagicMock()) as mock_god:
            # Add plugin to active set
            manager._Manager__active_plugins.add(mock_plugin)

            await manager._on_plugin_event(mock_event)

            # Verify god merging was called
            mock_god.__iadd__.assert_called_once_with(mock_plugin.sub_god)

        # Plugin should be removed from active set
        assert mock_plugin not in manager._Manager__active_plugins

    @pytest.mark.asyncio
    async def test_on_plugin_event_error(self, manager):
        """Test handling plugin error event."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_event = MagicMock()
        mock_event.event_type = EventType.PROCESSING_ERROR
        mock_event.plugin_instance = mock_plugin

        # Add plugin to active set
        manager._Manager__active_plugins.add(mock_plugin)

        await manager._on_plugin_event(mock_event)

        # Plugin should be removed from active set
        assert mock_plugin not in manager._Manager__active_plugins

    @pytest.mark.asyncio
    async def test_on_plugin_event_stopped(self, manager):
        """Test handling plugin stopped event."""
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_event = MagicMock()
        mock_event.event_type = EventType.PROCESSING_STOPPED
        mock_event.plugin_instance = mock_plugin

        # Add plugin to active set
        manager._Manager__active_plugins.add(mock_plugin)

        await manager._on_plugin_event(mock_event)

        # Plugin should be removed from active set
        assert mock_plugin not in manager._Manager__active_plugins

    @pytest.mark.asyncio
    async def test_on_plugin_event_progress(self, manager):
        """Test handling plugin progress event."""
        from indu_doc.plugins.events import ProcessingProgressEvent
        mock_plugin = MagicMock(spec=InduDocPlugin)
        mock_event = ProcessingProgressEvent("test", mock_plugin, 50, 100, "test.pdf")

        await manager._on_plugin_event(mock_event)

        assert manager._file_progress["test.pdf"] == 50.0