"""
Plugin event system for async event-driven processing.
"""
from typing import Any, Dict, List, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that plugins can emit."""
    PROCESSING_STARTED = "processing_started"
    PROCESSING_PROGRESS = "processing_progress"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_ERROR = "processing_error"
    PROCESSING_STOPPED = "processing_stopped"


@dataclass
class PluginEvent:
    """Base event class for plugin events."""
    event_type: EventType
    plugin_name: str
    plugin_instance: Any
    data: Dict[str, Any]


@dataclass
class ProcessingStartedEvent(PluginEvent):
    """Event emitted when processing starts."""
    file_paths: tuple[str, ...]

    def __init__(self, plugin_name: str, plugin_instance: Any, file_paths: tuple[str, ...]):
        super().__init__(
            event_type=EventType.PROCESSING_STARTED,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            data={"file_paths": file_paths}
        )
        self.file_paths = file_paths


@dataclass
class ProcessingProgressEvent(PluginEvent):
    """Event emitted during processing progress."""
    current_page: int
    total_pages: int
    current_file: str
    percentage: float

    def __init__(self, plugin_name: str, plugin_instance: Any,
                 current_page: int, total_pages: int, current_file: str):
        percentage = (current_page / total_pages * 100) if total_pages > 0 else 0.0
        super().__init__(
            event_type=EventType.PROCESSING_PROGRESS,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            data={
                "current_page": current_page,
                "total_pages": total_pages,
                "current_file": current_file,
                "percentage": percentage
            }
        )
        self.current_page = current_page
        self.total_pages = total_pages
        self.current_file = current_file
        self.percentage = percentage


@dataclass
class ProcessingCompletedEvent(PluginEvent):
    """Event emitted when processing completes successfully."""
    processed_files: tuple[str, ...]
    extracted_data: Any

    def __init__(self, plugin_name: str, plugin_instance: Any,
                 processed_files: tuple[str, ...], extracted_data: Any):
        super().__init__(
            event_type=EventType.PROCESSING_COMPLETED,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            data={
                "processed_files": processed_files,
                "extracted_data": extracted_data
            }
        )
        self.processed_files = processed_files
        self.extracted_data = extracted_data


@dataclass
class ProcessingErrorEvent(PluginEvent):
    """Event emitted when processing encounters an error."""
    error: Exception
    error_message: str

    def __init__(self, plugin_name: str, plugin_instance: Any, error: Exception):
        super().__init__(
            event_type=EventType.PROCESSING_ERROR,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            data={
                "error": error,
                "error_message": str(error)
            }
        )
        self.error = error
        self.error_message = str(error)


@dataclass
class ProcessingStoppedEvent(PluginEvent):
    """Event emitted when processing is stopped."""
    reason: str

    def __init__(self, plugin_name: str, plugin_instance: Any, reason: str = "stopped by user"):
        super().__init__(
            event_type=EventType.PROCESSING_STOPPED,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            data={"reason": reason}
        )
        self.reason = reason


class EventEmitter:
    """Async event emitter for plugins."""

    def __init__(self):
        self._listeners: Dict[EventType, List[Callable[[PluginEvent], Awaitable[None]]]] = {}
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def on(self, event_type: EventType, listener: Callable[[PluginEvent], Awaitable[None]]):
        """Register an event listener."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def off(self, event_type: EventType, listener: Callable[[PluginEvent], Awaitable[None]]):
        """Remove an event listener."""
        if event_type in self._listeners:
            self._listeners[event_type].remove(listener)

    async def emit(self, event: PluginEvent):
        """Emit an event to all registered listeners."""
        if event.event_type in self._listeners:
            tasks = []
            for listener in self._listeners[event.event_type]:
                try:
                    tasks.append(listener(event))
                except Exception as e:
                    logger.error(f"Error in event listener for {event.event_type}: {e}")

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def emit_sync(self, event: PluginEvent):
        """Emit an event synchronously (for use in non-async contexts)."""
        if self._loop.is_running():
            # If loop is running, schedule the emit
            asyncio.create_task(self.emit(event))
        else:
            # If no loop running, run it
            asyncio.run(self.emit(event))