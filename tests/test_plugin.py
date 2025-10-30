"""
Tests for the Plugin module.

This module tests the InduDocPlugin base class and its methods.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from indu_doc.plugins.plugin import InduDocPlugin
from indu_doc.configs import AspectsConfig
from indu_doc.plugins.plugins_common import ProcessingState
from indu_doc.plugins.events import (
    EventEmitter,
)
from indu_doc.god import God


class TestInduDocPlugin:
    """Test InduDocPlugin base class."""

    @pytest.fixture
    def mock_configs(self):
        """Create mock AspectsConfig."""
        return MagicMock(spec=AspectsConfig)

    @pytest.fixture
    def plugin(self, mock_configs):
        """Create a concrete plugin implementation for testing."""
        class ConcretePlugin(InduDocPlugin):
            def __init__(self, configs):
                super().__init__(configs)

            async def process_files_async(self, paths):
                return self.sub_god

            def get_supported_file_extensions(self):
                return ("pdf", "docx")

        return ConcretePlugin(mock_configs)

    def test_init(self, plugin, mock_configs):
        """Test plugin initialization."""
        assert isinstance(plugin.sub_god, God)
        assert plugin._processing_state == ProcessingState.IDLE
        assert isinstance(plugin.event_emitter, EventEmitter)
        assert plugin._current_page == 0
        assert plugin._total_pages == 0
        assert plugin._current_file is None
        assert plugin._error_message is None

    def test_event_emitter_property(self, plugin):
        """Test event emitter property."""
        assert plugin.event_emitter is plugin._event_emitter

    @pytest.mark.asyncio
    async def test_start_success(self, plugin):
        """Test successful plugin start."""
        test_paths = ("file1.pdf", "file2.pdf")

        with patch.object(plugin, 'process_files_async', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = plugin.sub_god

            await plugin.start(test_paths)

            assert plugin._processing_state == ProcessingState.IDLE
            mock_process.assert_called_once_with(test_paths)

    @pytest.mark.asyncio
    async def test_start_already_processing(self, plugin):
        """Test start fails when already processing."""
        plugin._processing_state = ProcessingState.PROCESSING

        with pytest.raises(RuntimeError, match="Cannot start processing"):
            await plugin.start(("file.pdf",))

    @pytest.mark.asyncio
    async def test_start_with_exception(self, plugin):
        """Test start handles exceptions properly."""
        test_paths = ("file1.pdf",)

        with patch.object(plugin, 'process_files_async', new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = ValueError("Test error")

            with pytest.raises(ValueError):
                await plugin.start(test_paths)

            assert plugin._processing_state == ProcessingState.ERROR
            assert plugin._error_message == "Test error"

    @pytest.mark.asyncio
    async def test_start_cancelled(self, plugin):
        """Test start handles cancellation."""
        test_paths = ("file1.pdf",)

        with patch.object(plugin, 'process_files_async', new_callable=AsyncMock) as mock_process:
            mock_process.side_effect = asyncio.CancelledError()

            with pytest.raises(asyncio.CancelledError):
                await plugin.start(test_paths)

            assert plugin._processing_state == ProcessingState.IDLE

    @pytest.mark.asyncio
    async def test_stop_processing(self, plugin):
        """Test stopping processing."""
        plugin._processing_state = ProcessingState.PROCESSING

        result = await plugin.stop()
        assert result is True
        assert plugin._processing_state == ProcessingState.STOPPING

    @pytest.mark.asyncio
    async def test_stop_not_processing(self, plugin):
        """Test stop when not processing."""
        plugin._processing_state = ProcessingState.IDLE

        result = await plugin.stop()
        assert result is False

    def test_abstract_methods_not_implemented(self):
        """Test that abstract methods are properly defined."""
        # This test ensures the abstract methods exist and are abstract
        assert hasattr(InduDocPlugin, 'get_supported_file_extensions')
        assert hasattr(InduDocPlugin, 'process_files_async')

    def test_get_state_progress_idle(self, plugin):
        """Test getting state progress when idle."""
        plugin._current_page = 0
        plugin._total_pages = 10
        plugin._current_file = "test.pdf"

        state = plugin.get_state_progress()

        assert state["state"] == "idle"
        assert state["progress"]["current_page"] == 0
        assert state["progress"]["total_pages"] == 10
        assert state["progress"]["current_file"] == "test.pdf"
        assert state["progress"]["percentage"] == 0.0
        assert state["progress"]["is_done"] is True
        assert state["error_message"] == ""

    def test_get_state_progress_processing(self, plugin):
        """Test getting state progress when processing."""
        plugin._processing_state = ProcessingState.PROCESSING
        plugin._current_page = 5
        plugin._total_pages = 10
        plugin._current_file = "test.pdf"

        state = plugin.get_state_progress()

        assert state["state"] == "processing"
        assert state["progress"]["percentage"] == 50.0
        assert state["progress"]["is_done"] is False

    def test_get_state_progress_zero_total_pages(self, plugin):
        """Test getting state progress with zero total pages."""
        plugin._current_page = 1
        plugin._total_pages = 0

        state = plugin.get_state_progress()
        assert state["progress"]["percentage"] == 0.0

    def test_is_done_idle(self, plugin):
        """Test is_done when idle."""
        plugin._processing_state = ProcessingState.IDLE
        assert plugin.is_done() is True

    def test_is_done_processing(self, plugin):
        """Test is_done when processing."""
        plugin._processing_state = ProcessingState.PROCESSING
        assert plugin.is_done() is False

    def test_is_done_stopping(self, plugin):
        """Test is_done when stopping."""
        plugin._processing_state = ProcessingState.STOPPING
        assert plugin.is_done() is False

    def test_reset(self, plugin):
        """Test plugin reset."""
        # Set some state
        plugin._processing_state = ProcessingState.PROCESSING
        plugin._current_page = 5
        plugin._total_pages = 10
        plugin._current_file = "test.pdf"
        plugin._error_message = "error"

        plugin.reset()

        assert plugin._processing_state == ProcessingState.IDLE
        assert plugin._current_page == 0
        assert plugin._total_pages == 0
        assert plugin._current_file is None
        assert plugin._error_message is None