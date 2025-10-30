"""
Tests for the Events module.

This module tests the event system including EventEmitter and all event classes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from indu_doc.plugins.events import (
    EventType,
    PluginEvent,
    ProcessingStartedEvent,
    ProcessingProgressEvent,
    ProcessingCompletedEvent,
    ProcessingErrorEvent,
    ProcessingStoppedEvent,
    EventEmitter
)


class TestEventType:
    """Test EventType enum."""

    def test_event_types(self):
        """Test all event types are defined."""
        assert EventType.PROCESSING_STARTED.value == "processing_started"
        assert EventType.PROCESSING_PROGRESS.value == "processing_progress"
        assert EventType.PROCESSING_COMPLETED.value == "processing_completed"
        assert EventType.PROCESSING_ERROR.value == "processing_error"
        assert EventType.PROCESSING_STOPPED.value == "processing_stopped"


class TestPluginEvent:
    """Test PluginEvent base class."""

    def test_plugin_event_creation(self):
        """Test creating a PluginEvent."""
        mock_plugin = MagicMock()
        event = PluginEvent(
            event_type=EventType.PROCESSING_STARTED,
            plugin_name="TestPlugin",
            plugin_instance=mock_plugin,
            data={"test": "data"}
        )

        assert event.event_type == EventType.PROCESSING_STARTED
        assert event.plugin_name == "TestPlugin"
        assert event.plugin_instance == mock_plugin
        assert event.data == {"test": "data"}


class TestProcessingStartedEvent:
    """Test ProcessingStartedEvent."""

    def test_processing_started_event(self):
        """Test ProcessingStartedEvent creation."""
        mock_plugin = MagicMock()
        file_paths = ("file1.pdf", "file2.pdf")

        event = ProcessingStartedEvent("TestPlugin", mock_plugin, file_paths)

        assert event.event_type == EventType.PROCESSING_STARTED
        assert event.plugin_name == "TestPlugin"
        assert event.plugin_instance == mock_plugin
        assert event.file_paths == file_paths
        assert event.data["file_paths"] == file_paths


class TestProcessingProgressEvent:
    """Test ProcessingProgressEvent."""

    def test_processing_progress_event(self):
        """Test ProcessingProgressEvent creation."""
        mock_plugin = MagicMock()

        event = ProcessingProgressEvent("TestPlugin", mock_plugin, 50, 100, "test.pdf")

        assert event.event_type == EventType.PROCESSING_PROGRESS
        assert event.plugin_name == "TestPlugin"
        assert event.plugin_instance == mock_plugin
        assert event.current_page == 50
        assert event.total_pages == 100
        assert event.current_file == "test.pdf"
        assert event.percentage == 50.0

    def test_processing_progress_event_zero_total_pages(self):
        """Test ProcessingProgressEvent with zero total pages."""
        mock_plugin = MagicMock()

        event = ProcessingProgressEvent("TestPlugin", mock_plugin, 1, 0, "test.pdf")

        assert event.percentage == 0.0


class TestProcessingCompletedEvent:
    """Test ProcessingCompletedEvent."""

    def test_processing_completed_event(self):
        """Test ProcessingCompletedEvent creation."""
        mock_plugin = MagicMock()
        mock_data = MagicMock()
        processed_files = ("file1.pdf", "file2.pdf")

        event = ProcessingCompletedEvent("TestPlugin", mock_plugin, processed_files, mock_data)

        assert event.event_type == EventType.PROCESSING_COMPLETED
        assert event.plugin_name == "TestPlugin"
        assert event.plugin_instance == mock_plugin
        assert event.processed_files == processed_files
        assert event.extracted_data == mock_data


class TestProcessingErrorEvent:
    """Test ProcessingErrorEvent."""

    def test_processing_error_event(self):
        """Test ProcessingErrorEvent creation."""
        mock_plugin = MagicMock()
        test_error = ValueError("Test error")

        event = ProcessingErrorEvent("TestPlugin", mock_plugin, test_error)

        assert event.event_type == EventType.PROCESSING_ERROR
        assert event.plugin_name == "TestPlugin"
        assert event.plugin_instance == mock_plugin
        assert event.error == test_error
        assert event.error_message == "Test error"


class TestProcessingStoppedEvent:
    """Test ProcessingStoppedEvent."""

    def test_processing_stopped_event(self):
        """Test ProcessingStoppedEvent creation."""
        mock_plugin = MagicMock()

        event = ProcessingStoppedEvent("TestPlugin", mock_plugin, "user request")

        assert event.event_type == EventType.PROCESSING_STOPPED
        assert event.plugin_name == "TestPlugin"
        assert event.plugin_instance == mock_plugin
        assert event.reason == "user request"

    def test_processing_stopped_event_default_reason(self):
        """Test ProcessingStoppedEvent with default reason."""
        mock_plugin = MagicMock()

        event = ProcessingStoppedEvent("TestPlugin", mock_plugin)

        assert event.reason == "stopped by user"


class TestEventEmitter:
    """Test EventEmitter class."""

    @pytest.fixture
    def emitter(self):
        """Create EventEmitter instance."""
        return EventEmitter()

    def test_init(self, emitter):
        """Test EventEmitter initialization."""
        assert emitter._listeners == {}

    def test_on_add_listener(self, emitter):
        """Test adding an event listener."""
        mock_listener = AsyncMock()

        emitter.on(EventType.PROCESSING_STARTED, mock_listener)

        assert EventType.PROCESSING_STARTED in emitter._listeners
        assert mock_listener in emitter._listeners[EventType.PROCESSING_STARTED]

    def test_on_multiple_listeners(self, emitter):
        """Test adding multiple listeners for the same event."""
        mock_listener1 = AsyncMock()
        mock_listener2 = AsyncMock()

        emitter.on(EventType.PROCESSING_STARTED, mock_listener1)
        emitter.on(EventType.PROCESSING_STARTED, mock_listener2)

        assert len(emitter._listeners[EventType.PROCESSING_STARTED]) == 2

    def test_off_remove_listener(self, emitter):
        """Test removing an event listener."""
        mock_listener = AsyncMock()
        emitter.on(EventType.PROCESSING_STARTED, mock_listener)

        emitter.off(EventType.PROCESSING_STARTED, mock_listener)

        assert mock_listener not in emitter._listeners[EventType.PROCESSING_STARTED]

    def test_off_nonexistent_event(self, emitter):
        """Test removing listener from nonexistent event."""
        mock_listener = AsyncMock()

        # Should not raise an error
        emitter.off(EventType.PROCESSING_STARTED, mock_listener)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_emit_no_listeners(self, emitter):
        """Test emitting event with no listeners."""
        mock_plugin = MagicMock()
        event = ProcessingStartedEvent("TestPlugin", mock_plugin, ("file.pdf",))

        # Should not raise an error
        await emitter.emit(event)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_emit_with_listeners(self, emitter):
        """Test emitting event with listeners."""
        mock_listener1 = AsyncMock()
        mock_listener2 = AsyncMock()
        mock_plugin = MagicMock()
        event = ProcessingStartedEvent("TestPlugin", mock_plugin, ("file.pdf",))

        emitter.on(EventType.PROCESSING_STARTED, mock_listener1)
        emitter.on(EventType.PROCESSING_STARTED, mock_listener2)

        await emitter.emit(event)

        mock_listener1.assert_called_once_with(event)
        mock_listener2.assert_called_once_with(event)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_emit_listener_exception(self, emitter):
        """Test emitting event when listener raises exception."""
        mock_listener = AsyncMock(side_effect=ValueError("Test error"))
        mock_plugin = MagicMock()
        event = ProcessingStartedEvent("TestPlugin", mock_plugin, ("file.pdf",))

        emitter.on(EventType.PROCESSING_STARTED, mock_listener)

        # Should not raise the exception from the listener
        await emitter.emit(event)

        mock_listener.assert_called_once_with(event)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_emit_multiple_events(self, emitter):
        """Test emitting different types of events."""
        mock_started_listener = AsyncMock()
        mock_completed_listener = AsyncMock()
        mock_plugin = MagicMock()

        emitter.on(EventType.PROCESSING_STARTED, mock_started_listener)
        emitter.on(EventType.PROCESSING_COMPLETED, mock_completed_listener)

        started_event = ProcessingStartedEvent("TestPlugin", mock_plugin, ("file.pdf",))
        completed_event = ProcessingCompletedEvent("TestPlugin", mock_plugin, ("file.pdf",), MagicMock())

        await emitter.emit(started_event)
        await emitter.emit(completed_event)

        mock_started_listener.assert_called_once_with(started_event)
        mock_completed_listener.assert_called_once_with(completed_event)