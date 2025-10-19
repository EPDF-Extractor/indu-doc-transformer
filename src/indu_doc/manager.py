from typing import Any
import logging
import asyncio
from indu_doc.configs import AspectsConfig
from indu_doc.god import God, PageMapperEntry
from indu_doc.plugins.plugin import InduDocPlugin
from indu_doc.plugins.plugins_common import ProcessingState
from indu_doc.plugins.events import EventType, PluginEvent, ProcessingProgressEvent
from indu_doc.xtarget import XTarget
import os

logger = logging.getLogger(__name__)



class Manager:
    """
    Main manager class for coordinating document processing plugins.

    The Manager is responsible for:
    - Loading configuration files
    - Registering and managing processing plugins
    - Coordinating document processing across multiple plugins
    - Monitoring processing state and progress
    - Providing access to extracted data and statistics

    :ivar configs: Configuration object containing aspect and processing settings.
    :ivar god: Main God instance containing all extracted data.
    :ivar plugins: List of registered plugin instances.
    :ivar __active_plugins: Internal set of plugins currently processing.
    """

    def __init__(self, configs: AspectsConfig) -> None:
        """
        Initialize the Manager with configuration.

        :param configs: Configuration object for aspects and processing settings.
        :type configs: AspectsConfig
        """
        self.configs: AspectsConfig = configs
        self.god: God = God(self.configs)
        self.plugins: list[InduDocPlugin] = []

        # Active plugins currently processing
        self.__active_plugins: set[InduDocPlugin] = set()

        # Event listeners for plugin completion
        self.__completion_event = asyncio.Event()

        # File progress tracking
        self._file_progress: dict[str, float] = {}

    async def _on_plugin_event(self, event: PluginEvent) -> None:
        """
        Handle plugin events.

        :param event: The plugin event that occurred.
        :type event: PluginEvent
        """
        if event.event_type == EventType.PROCESSING_COMPLETED:
            logger.info(f"Plugin {event.plugin_name} completed processing")
            self.god += event.plugin_instance.sub_god  # Merge data
            event.plugin_instance.reset()  # Reset plugin
            self.__active_plugins.discard(event.plugin_instance)

            # Set completion event if no more active plugins
            if not self.__active_plugins:
                self.__completion_event.set()

        elif event.event_type == EventType.PROCESSING_ERROR:
            logger.error(f"Plugin {event.plugin_name} encountered error: {event.data.get('error_message', '')}")
            event.plugin_instance.reset()
            self.__active_plugins.discard(event.plugin_instance)

            # Set completion event if no more active plugins
            if not self.__active_plugins:
                self.__completion_event.set()

        elif event.event_type == EventType.PROCESSING_STOPPED:
            logger.info(f"Plugin {event.plugin_name} processing stopped")
            event.plugin_instance.reset()
            self.__active_plugins.discard(event.plugin_instance)

            # Set completion event if no more active plugins
            if not self.__active_plugins:
                self.__completion_event.set()

        elif event.event_type == EventType.PROCESSING_PROGRESS:
            if isinstance(event, ProcessingProgressEvent):
                self._file_progress[event.current_file] = event.percentage

    @classmethod
    def from_config_files(cls, config_path: str) -> "Manager":
        """
        Create a Manager instance from a configuration file.

        :param config_path: Path to the configuration file.
        :type config_path: str
        :returns: New Manager instance initialized with the configuration.
        :rtype: Manager
        """
        configs = AspectsConfig.init_from_file(config_path)
        return cls(configs)

    def register_plugin(self, plugin: InduDocPlugin) -> None:
        """
        Register a plugin with the manager.

        :param plugin: The plugin instance to register.
        :type plugin: InduDocPlugin
        """
        self.plugins.append(plugin)
        # Register event listeners for all event types
        plugin.event_emitter.on(EventType.PROCESSING_COMPLETED, self._on_plugin_event)
        plugin.event_emitter.on(EventType.PROCESSING_ERROR, self._on_plugin_event)
        plugin.event_emitter.on(EventType.PROCESSING_STOPPED, self._on_plugin_event)
        plugin.event_emitter.on(EventType.PROCESSING_PROGRESS, self._on_plugin_event)
    
    def _distribute_files_to_plugins(self, file_paths: tuple[str, ...]) -> dict[InduDocPlugin, tuple[str, ...]]:
        """
        Distribute files to appropriate plugins based on supported extensions.
        
        :param file_paths: Tuple of file paths to distribute
        :return: Dictionary mapping plugins to their assigned files
        """
        distribution = {}
        remaining_files = set(file_paths)
        
        for plugin in self.plugins:
            supported_extensions = tuple(ext.lower() for ext in plugin.get_supported_file_extensions())
            plugin_files = tuple(
                f for f in remaining_files 
                if any(f.lower().endswith(ext) for ext in supported_extensions)
            )
            
            if plugin_files:
                distribution[plugin] = plugin_files
                remaining_files -= set(plugin_files)
        
        if remaining_files:
            logger.warning(f"No plugin found to process files: {remaining_files}")
        
        return distribution

    async def process_files_async(self, file_paths: str | tuple[str, ...]) -> None:
        """
        Start processing the given files using all registered plugins asynchronously.

        Files are distributed to plugins based on their supported file extensions.
        Each plugin receives only the files it can handle.

        :param file_paths: Path or tuple of paths to files to process.
        :type file_paths: str | tuple[str, ...]
        :raises FileNotFoundError: If any of the specified files do not exist
        """
        if not isinstance(file_paths, tuple):
            file_paths = (file_paths,)

        # Validate that all files exist
        missing_files = [f for f in file_paths if not os.path.exists(f)]
        if missing_files:
            raise FileNotFoundError(f"The following files do not exist: {missing_files}")
        # convert all paths to absolute paths
        file_paths = tuple(os.path.abspath(f) for f in file_paths)

        # Initialize file progress
        self._file_progress = {file: 0.0 for file in file_paths}

        file_distribution = self._distribute_files_to_plugins(file_paths)

        # Reset completion event
        self.__completion_event.clear()

        # Start all plugins
        for plugin, plugin_files in file_distribution.items():
            logger.info(f"Starting processing with plugin {plugin.__class__.__name__} for files: {plugin_files}")
            await plugin.start(plugin_files)
            self.__active_plugins.add(plugin)

    def process_files(self, file_paths: str | tuple[str, ...], blocking: bool = False) -> None:
        """
        Start processing the given files using all registered plugins.

        Files are distributed to plugins based on their supported file extensions.
        Each plugin receives only the files it can handle.

        :param file_paths: Path or tuple of paths to files to process.
        :type file_paths: str | tuple[str, ...]
        :param blocking: If True, wait for completion before returning.
        :type blocking: bool
        :raises FileNotFoundError: If any of the specified files do not exist
        """
        try:
            # Try to get current running loop
            asyncio.get_running_loop()
            # If we have a running loop, create task
            asyncio.create_task(self.process_files_async(file_paths))
        except RuntimeError:
            # No running loop, run synchronously
            asyncio.run(self.process_files_async(file_paths))

        if blocking:
            asyncio.run(self.wait_for_completion_async())

    async def wait_for_completion_async(self, timeout: float | None = None) -> bool:
        """
        Wait for all plugin processing to complete asynchronously.

        :param timeout: Maximum time to wait in seconds, None for no timeout
        :return: True if all processing completed, False if timeout occurred
        """
        try:
            await asyncio.wait_for(self.__completion_event.wait(), timeout=timeout)
            logger.info("All plugins completed processing")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for plugin completion after {timeout} seconds")
            return False

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """
        Wait for all plugin processing to complete.

        :param timeout: Maximum time to wait in seconds, None for no timeout
        :return: True if all processing completed, False if timeout occurred
        """
        try:
            # Try to get current running loop
            asyncio.get_running_loop()
            # If we have a running loop, this might be problematic
            # For backward compatibility, we'll run it in a new loop if needed
            return asyncio.run(self.wait_for_completion_async(timeout))
        except RuntimeError:
            # No running loop
            return asyncio.run(self.wait_for_completion_async(timeout))

    def get_active_plugins(self) -> tuple[InduDocPlugin,...]:
        """
        Get list of plugins currently processing files.
        
        :return: List of plugins that are actively processing
        """
        return tuple(self.__active_plugins)
    
    def has_errors(self) -> bool:
        """
        Check if any registered plugins are in an error state.
        
        :return: True if any plugin has errors, False otherwise
        """
        states = self.get_processing_state()
        return any(state.get('state') == 'error' for state in states)

    def get_processing_state(self) -> list[dict[str, Any]]:
        """
        Get the current processing state and progress information.

        :returns: List of dictionaries containing processing state for each plugin.
        :rtype: list[dict[str, Any]]

        Each dictionary contains:
        - ``state``: Current processing state
        - ``progress``: Dict with current_page, total_pages, current_file
        - ``error_message``: Error message if state is ERROR
        """
        states = []
        for plugin in self.plugins:
            state_info = plugin.get_state_progress()
            states.append(state_info)
        return states
    
    def get_file_progress(self) -> dict[str, float]:
        """
        Get the current progress percentage for each file being processed.

        :returns: Dictionary mapping file paths to their progress percentage (0.0 to 100.0).
        :rtype: dict[str, float]
        """
        return self._file_progress.copy()
    
    def is_processing(self) -> bool:
        """
        Check if any plugin is currently processing files.
        
        :return: True if any plugin is processing, False otherwise
        """
        return any(p._processing_state == ProcessingState.PROCESSING or p._processing_state == ProcessingState.STOPPING for p in self.plugins)
    
    def stop_processing(self) -> None:
        """
        Stop all currently processing plugins.
        """
        for p in self.plugins:
            p.stop()
    def update_configs(self, configs: AspectsConfig) -> None:
        """
        Update the manager's configuration.

        **WARNING:** This will remove all existing data and start fresh with the new configs.
        Cannot be called while processing is running.

        :param configs: New configuration object.
        :type configs: AspectsConfig
        :raises RuntimeError: If called while processing is active.
        """
        if self.is_processing():
            raise RuntimeError("Cannot update configs while processing is running.")
        
        if configs != self.configs:
            logger.info("Updating configs and resetting all data.")
            self.configs = configs
            self.god = God(self.configs)
            # Clear file progress tracking
            self._file_progress.clear()
            for plugin in self.plugins:
                plugin.reset()

    def get_tree(self) -> Any:
        # form tree of objects by aspects. Level of the tree is aspect priority
        all_aspects = [(t, t.tag.get_aspects())
                      for t in self.god.xtargets.values()]
        # convert the parts into a prefex tree structure
        """
        tree_data = [
        {'id': 'A', 'children': [{'id': 'A1'}, {'id': 'A2', 'description': 't.tag.tag_str'}]},
        {'id': 'B', 'children': [{'id': 'B1'}, {'id': 'B2', 'description': 't.tag.tag_str'}]},
        ]
        """
        raw_tree: dict[str, Any] = {}
        for t, aspects in all_aspects:
            current_level = raw_tree
            if aspects:
                for sep in self.configs.separators:
                    if sep in aspects:
                        for aspect in aspects[sep]:
                            TreeKey = str(aspect)
                            if TreeKey not in current_level:
                                current_level[TreeKey] = {"_aspect": aspect}
                            current_level = current_level[TreeKey]

            # at the leaf, we can store the full tag string or other info
            if "_targets" not in current_level:
                current_level["_targets"] = set()
            current_level["_targets"].add(t)

        return raw_tree or []

    def save_to_db(self) -> None:
        raise NotImplementedError("Save on DB not implemented yet")

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about the current state of the Manager.

        :returns: Dictionary containing statistics such as number of objects and connections.
        :rtype: dict[str, Any]

        The returned dictionary includes counts for:
        - ``num_xtargets``: Number of XTarget objects
        - ``num_connections``: Number of Connection objects
        - ``num_attributes``: Number of Attribute objects
        - ``num_links``: Number of Link objects
        - ``num_pins``: Number of Pin objects
        - ``num_aspects``: Number of Aspect objects
        - ``processing_states``: Current processing states from all plugins
        """
        base_stats : dict[str, Any] = {
            "num_xtargets": len(self.god.xtargets),
            "num_connections": len(self.god.connections),
            "num_attributes": len(self.god.attributes),
            "num_links": len(self.god.links),
            "num_pins": len(self.god.pins),
            "num_aspects": len(self.god.aspects)
        }

        # Add processing state info
        processing_states = []
        for plugin in self.plugins:
            state_info = plugin.get_state_progress()
            processing_states.append(state_info)
            
        base_stats["processing_states"] = processing_states
        return base_stats

    def get_xtargets(self) -> list[XTarget]:
        return list(self.god.xtargets.values())

    def get_connections(self) -> list:
        return list(self.god.connections.values())

    def get_attributes(self) -> list:
        return list(self.god.attributes.values())

    def get_links(self) -> list:
        return list(self.god.links.values())

    def get_pins(self) -> list:
        return list(self.god.pins.values())

    def get_target_pages_by_tag(self, tag_str: str):
        if not tag_str:
            return None

        # Find target by tag_str
        target = next(
            (t for t in self.god.xtargets.values() if t.tag.tag_str == tag_str), None)
        if not target:
            return None

        pages = self.god.get_pages_of_object(target)

        return {
            "target": target,
            "pages": pages
        }

    def get_connection_details(self, guid: str):
        """Get detailed information about a connection by its GUID."""
        if not guid or guid not in self.god.connections:
            return None

        connection = self.god.connections[guid]
        pages = self.god.get_pages_of_object(connection)

        return {
            "connection": connection,
            "pages": pages
        }

    def get_pages_of_object(self, id: str) -> set[PageMapperEntry]:
        return self.god.get_pages_of_object(id)

    def get_objects_on_page(self, page_num: int, file_path: str) -> list:
        """Get all objects that appear on a specific page."""
        objects = self.god.get_objects_on_page(page_num, file_path)
        return list(objects)

    @property
    def has_data(self) -> bool:
        """
        Check if there is any extracted data.

        :returns: True if any XTarget objects have been extracted, False otherwise.
        :rtype: bool
        """
        return len(self.god.xtargets) > 0
            
if __name__ == "__main__":
    import sys
    import os
    
    logging.basicConfig(
        level=logging.INFO,  
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        manager = Manager.from_config_files("config.json")
        from indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin import EplanPDFPlugin
        
        pdfPlugin = EplanPDFPlugin.from_config_files('config.json',"extraction_settings.json")
        manager.register_plugin(pdfPlugin)

        pdf_path = "pdfs\\sample_small_small.pdf"
        if not os.path.exists(pdf_path):
            print(f"Error: PDF file not found: {pdf_path}")
            print("Please ensure the PDF file exists before running.")
            sys.exit(1)
        
        print(f"Starting processing of: {pdf_path}")
        try:
            manager.process_files(pdf_path)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        
        # Monitor progress during processing
        import time
        print("Monitoring file progress...")
        start_time = time.time()
        while not manager.wait_for_completion(timeout=1):  # Check every 1 second
            elapsed = time.time() - start_time
            progress = manager.get_file_progress()
            if progress:
                print(f"[{elapsed:.1f}s] Current file progress:")
                for file_path, pct in progress.items():
                    print(f"  {os.path.basename(file_path)}: {pct:.1f}%")
            else:
                print(f"[{elapsed:.1f}s] No progress data available yet...")
        
        if manager.has_errors():
            print("Processing completed but with errors:")
            states = manager.get_processing_state()
            for state in states:
                if state.get('state') == 'error':
                    print(f"  - {state.get('error_message')}")
            sys.exit(1)
        else:
            total_time = time.time() - start_time
            print(f"Processing completed successfully in {total_time:.1f} seconds")
            stats = manager.get_stats()
            print("Extracted Data Statistics:")
            for key, value in stats.items():
                print(f"  - {key}: {value}")
            # Show final progress
            final_progress = manager.get_file_progress()
            if final_progress:
                print("Final file progress:")
                for file_path, pct in final_progress.items():
                    print(f"  {os.path.basename(file_path)}: {pct:.1f}%")
            
    except Exception as e:
        print(f"Error running manager: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
