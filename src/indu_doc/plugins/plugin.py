from abc import ABC, abstractmethod
import asyncio
from typing import Optional, Any, Callable
from indu_doc.configs import AspectsConfig
from indu_doc.god import God
from indu_doc.plugins.plugins_common import ProcessingState
from indu_doc.plugins.events import (
    EventEmitter, ProcessingStartedEvent, ProcessingCompletedEvent, ProcessingErrorEvent, ProcessingStoppedEvent
)


class InduDocPlugin(ABC):
    """
    Abstract base class for InduDoc plugins.

    This class provides the interface and common functionality for all plugins
    in the InduDoc system. Plugins are responsible for processing documents
    and extracting information from them.

    :param configs: The AspectsConfig instance providing configuration for aspects.
    :type configs: AspectsConfig

    :ivar sub_god: A temporary God only local to this plugin.
    :ivar _processing_state: Current processing state from ProcessingState enum.
    :ivar _event_emitter: Event emitter for async event handling.
    :ivar _processing_task: Current processing task if running.
    """

    def __init__(self, configs: AspectsConfig, **kwargs):
        """
        Initialize the plugin with the God instance.

        :param configs: The AspectsConfig instance providing configuration for aspects.
        :type configs: AspectsConfig
        """
        self.sub_god = God(configs)
        self._processing_state = ProcessingState.IDLE
        self._event_emitter = EventEmitter()
        self._processing_task: Optional[asyncio.Task] = None
        
        # Progress tracking
        self._current_page = 0
        self._total_pages = 0
        self._current_file: Optional[str] = None
        self._error_message: Optional[str] = None

    @property
    def event_emitter(self) -> EventEmitter:
        """Get the event emitter for this plugin."""
        return self._event_emitter

    @abstractmethod
    async def process_files_async(self, paths: tuple[str, ...]) -> Any:
        """
        Async method to process the given file paths.

        This method should perform the actual document processing and emit events
        as progress is made. The method should not manage state - that's handled
        by the base class.

        :param paths: Tuple of file paths to process.
        :type paths: tuple[str, ...]
        :returns: Extracted data from processing.
        :rtype: Any
        :raises NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError("Plugin subclasses must implement the process_files_async method.")

    async def __start_async(self, paths: tuple[str, ...]) -> None:
        """
        Start processing the given file paths asynchronously.

        This method manages the processing lifecycle and emits appropriate events.

        :param paths: Tuple of file paths to process.
        :type paths: tuple[str, ...]
        """
        if self._processing_state != ProcessingState.IDLE:
            raise RuntimeError(
                f"Cannot start processing: current state is {self._processing_state.value}")

        # Reset state and data
        self.sub_god.reset()
        self._processing_state = ProcessingState.PROCESSING
        self._current_page = 0
        self._total_pages = 0
        self._current_file = None
        self._error_message = None

        # Emit started event
        await self._event_emitter.emit(
            ProcessingStartedEvent(self.__class__.__name__, self, paths)
        )

        try:
            # Create and start processing task
            self._processing_task = asyncio.create_task(self.process_files_async(paths))
            extracted_data = await self._processing_task

            # Processing completed successfully
            self._processing_state = ProcessingState.IDLE
            await self._event_emitter.emit(
                ProcessingCompletedEvent(
                    self.__class__.__name__, self, paths, extracted_data
                )
            )

        except asyncio.CancelledError:
            # Processing was stopped
            self._processing_state = ProcessingState.IDLE
            await self._event_emitter.emit(
                ProcessingStoppedEvent(self.__class__.__name__, self, "cancelled")
            )
            raise

        except Exception as e:
            # Processing failed
            self._processing_state = ProcessingState.ERROR
            self._error_message = str(e)
            await self._event_emitter.emit(
                ProcessingErrorEvent(self.__class__.__name__, self, e)
            )
            raise

        finally:
            self._processing_task = None

    async def start(self, paths: tuple[str, ...]):
        """
        Start processing the given file paths.

        :param paths: Tuple of file paths to process.
        :type paths: tuple[str, ...]
        :param on_complete: Optional callback (deprecated - use event listeners).
        :type on_complete: Optional[Callable[[], None]]
        """
        await self.__start_async(paths)

    async def stop_async(self) -> bool:
        """
        Stop the current processing operation asynchronously.

        :returns: True if processing was stopped, False if not running.
        :rtype: bool
        """
        if self._processing_state == ProcessingState.PROCESSING and self._processing_task:
            self._processing_state = ProcessingState.STOPPING
            self._processing_task.cancel()

            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

            self._processing_state = ProcessingState.IDLE
            return True
        return False

    def stop(self) -> bool:
        """
        Stop the current processing operation.

        :returns: True if processing was stopped, False if not running.
        :rtype: bool
        """
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            self._processing_state = ProcessingState.IDLE
            return True
        return False


    @abstractmethod
    def get_supported_file_extensions(self) -> tuple[str, ...]:
        """
        Get the list of supported file extensions for this plugin.

        By default, returns an empty list. Subclasses can override this method
        to specify which file types they can handle.

        :returns: List of supported file extensions (e.g., ['.pdf', '.docx']).
        :rtype: tuple[str, ...]
        """
        return ()

    def get_state_progress(self) -> dict:
        """
        Get the current processing state and progress information.

        :returns: Dictionary containing processing state and progress details.
        :rtype: dict

        The returned dictionary contains the following keys:

        - ``state`` (:class:`str`): Current processing state value (e.g., 'idle', 'processing')
        - ``progress`` (dict): Progress information with keys:

          - ``current_page`` (int): Current page being processed
          - ``total_pages`` (int): Total number of pages
          - ``current_file`` (str or None): Path of currently processing file

        - ``error_message`` (str or None): Error message if state is ERROR
        """
        percentage = (self._current_page / self._total_pages * 100) if self._total_pages > 0 else 0.0
        return {
            "state": self._processing_state.value,
            "progress": {
                "current_page": self._current_page,
                "total_pages": self._total_pages,
                "current_file": self._current_file or "",
                "percentage": percentage,
                "is_done": self.is_done(),
            },
            "error_message": self._error_message or "",
        }

    def is_done(self) -> bool:
        """Check if no processing is currently running."""
        return self._processing_state not in [ProcessingState.PROCESSING, ProcessingState.STOPPING]

    def reset(self):
        """
        Reset the plugin's internal state and temporary God instance.
        """
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
        self.sub_god.reset()
        self._processing_state = ProcessingState.IDLE
        self._current_page = 0
        self._total_pages = 0
        self._current_file = None
        self._error_message = None