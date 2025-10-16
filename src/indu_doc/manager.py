from typing import Any
import threading
from enum import Enum

from pymupdf import pymupdf  # type: ignore
from tqdm import tqdm
import logging

from indu_doc.common_page_utils import detect_page_type
from indu_doc.configs import AspectsConfig
from indu_doc.god import God, PageMapperEntry
from indu_doc.page_processor import PageProcessor, PageInfo
from indu_doc.tag import Tag, Aspect
from indu_doc.xtarget import XTarget
from indu_doc.page_settings import PageSettings

logger = logging.getLogger(__name__)


class ProcessingState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    STOPPING = "stopping"
    ERROR = "error"


class Manager:
    def __init__(self, configs: AspectsConfig, settings: PageSettings) -> None:
        self.configs: AspectsConfig = configs
        self.god: God = God(self.configs)
        self.settings = settings
        self.page_processor: PageProcessor = PageProcessor(self.god, self.settings)

        # Threading and state management
        self._processing_thread: threading.Thread | None = None
        self._processing_state = ProcessingState.IDLE
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._progress_info = {
            "current_page": 0,
            "total_pages": 0,
            "current_file": "",
            "error_message": ""
        }

    @classmethod
    def from_config_files(cls, config_path: str, setup_path: str) -> "Manager":
        """_summary_

        Args:
            config_path (str): _description_
            setup_path  (str): _description_

        Returns:
            Manager: _description_
        """
        settings = PageSettings.init_from_file(setup_path)
        configs = AspectsConfig.init_from_file(config_path)
        return cls(configs, settings)

    def process_pdfs(self, pdf_paths: str | list[str], blocking: bool = False) -> None:
        """
        Start PDF processing in a separate thread.

        Args:
            blocking: If True, process in the current thread (blocking). If False, process in a new thread (non-blocking) and returns immediately, use get_processing_state() to monitor progress.

        """
        with self._state_lock:
            if self._processing_state != ProcessingState.IDLE:
                raise RuntimeError(
                    f"Cannot start processing: current state is {self._processing_state.value}")

            self._processing_state = ProcessingState.PROCESSING
            self._stop_event.clear()
            self._progress_info = {
                "current_page": 0,
                "total_pages": 0,
                "current_file": "",
                "error_message": ""
            }
        if blocking:
            # process in the current thread (blocking)
            self._process_pdfs_worker(pdf_paths)
            with self._state_lock:
                if self._processing_state == ProcessingState.PROCESSING:
                    self._processing_state = ProcessingState.IDLE
                    logger.info("PDF processing completed successfully")
            return

        # Start processing in a separate thread
        self._processing_thread = threading.Thread(
            target=self._process_pdfs_worker,
            args=(pdf_paths,),
            daemon=True
        )
        self._processing_thread.start()

    def _process_pdfs_worker(self, pdf_paths: str | list[str]) -> None:
        """Worker method that runs in a separate thread."""
        try:
            if not isinstance(pdf_paths, list):
                pdf_paths = [pdf_paths]

            docs = [pymupdf.open(p) for p in pdf_paths]

            # Calculate total pages
            total_pages = sum(len(doc) for doc in docs)
            self._progress_info["total_pages"] = total_pages

            current_page = 0

            for doc, file_path in zip(docs, pdf_paths):
                if self._stop_event.is_set():
                    break

                self._progress_info["current_file"] = file_path
                logger.info(f"Processing file: {file_path}")

                for page in doc:
                    if self._stop_event.is_set():
                        break

                    current_page += 1
                    self._progress_info["current_page"] = current_page

                    # type: ignore
                    logger.info(f"Processing page {page.number + 1}")
                    self.page_processor.run(page)

                doc.close()

            # Processing completed successfully
            with self._state_lock:
                if self._processing_state == ProcessingState.PROCESSING:
                    self._processing_state = ProcessingState.IDLE
                    logger.info("PDF processing completed successfully")

        except Exception as e:
            logger.error(f"Error during PDF processing: {str(e)}")
            with self._state_lock:
                self._processing_state = ProcessingState.ERROR
                self._progress_info["error_message"] = str(e)

    def stop_processing(self) -> bool:
        """
        Stop the current PDF processing.
        Returns True if stop was initiated, False if no processing was running.
        """
        with self._state_lock:
            if self._processing_state == ProcessingState.PROCESSING:
                self._processing_state = ProcessingState.STOPPING
                self._stop_event.set()
                logger.info("Stopping PDF processing...")
                return True
            return False

    def get_processing_state(self) -> dict[str, Any]:
        """
        Get the current processing state and progress information.

        Returns:
            dict containing:
            - state: current processing state
            - progress: dict with current_page, total_pages, current_file
            - error_message: error message if state is ERROR
        """
        with self._state_lock:
            # Check if thread has finished
            if (self._processing_thread and
                not self._processing_thread.is_alive() and
                    self._processing_state == ProcessingState.STOPPING):
                self._processing_state = ProcessingState.IDLE
                logger.info("PDF processing stopped")
            progress_percentage = (
                # type: ignore
                (self._progress_info["current_page"] /
                 self._progress_info["total_pages"])
                # type: ignore
                if self._progress_info["total_pages"] > 0 else 0.0
            )
            return {
                "state": self._processing_state.value,
                "progress": {
                    "current_page": self._progress_info["current_page"],
                    "total_pages": self._progress_info["total_pages"],
                    "current_file": self._progress_info["current_file"],
                    "percentage": progress_percentage
                },
                "error_message": self._progress_info["error_message"]
            }

    def is_processing(self) -> bool:
        """Check if PDF processing is currently running."""
        with self._state_lock:
            return self._processing_state in [ProcessingState.PROCESSING, ProcessingState.STOPPING]

    def update_configs(self, configs: AspectsConfig) -> None:
        """
        WARNING: This will remove all existing data and start fresh with the new configs.
        Cannot be called while processing is running.
        """
        if self.is_processing():
            raise RuntimeError(
                "Cannot update configs while processing is running")

        if configs != self.configs:
            logger.info("Updating configs and resetting all data.")

        self.configs = configs
        self.god = God(self.configs)
        self.page_processor = PageProcessor(self.god, self.settings)

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

        
        def get_gui_description(target: XTarget) -> str:
            lines = []
            lines.append(f"<div class='tree-description'>")
            lines.append(
                f"<div class='target-type'><strong>Type:</strong> <span class='badge'>{target.target_type.value.upper()}</span></div>")
            lines.append(
                f"<div class='target-tag'><strong>Tag:</strong> {target.tag.tag_str}</div>")
            lines.append(
                f"<div class='target-guid'><strong>GUID:</strong> <code>{target.get_guid()}</code></div>")
            if target.attributes:
                lines.append(
                    f"<div class='target-attributes'><strong>Attributes:</strong>")
                lines.append("<ul>")
                for attr in target.attributes:
                    lines.append(f"<li>{attr}</li>")
                lines.append("</ul></div>")
            lines.append("</div>")
            return "".join(lines)
        
        def get_aspect_gui_description(aspect: Aspect) -> str:
            lines = []
            lines.append(f"<div class='tree-description'>")
            if aspect.attributes:
                lines.append(
                    f"<div class='target-attributes'><strong>Attributes:</strong>")
                lines.append("<ul>")
                for attr in aspect.attributes:
                    lines.append(f"<li>{attr}</li>")
                lines.append("</ul></div>")
            lines.append("</div>")
            return "".join(lines)
            
        # convert raw_tree to the desired format for the GUI
        def convert_to_gui_format(node):
            if not isinstance(node, dict):
                return []

            gui_node = []
            sorted_keys = sorted(
                # sorted by 2 keys, to have _targets last and others alphabetically
                node.keys(), key=lambda k: (k in ("_targets", "_aspects"), k))
            for key in sorted_keys:
                child = node[key]
                if key == "_targets":
                    if not isinstance(child, set):
                        logger.debug(
                            f"Expected set of targets, got {type(child)}")
                        continue

                    for target in (c for c in child if isinstance(c, XTarget)):
                        gui_node.append(
                            {'id': target.tag.tag_str, 'description': get_gui_description(target), 'children': []})
                elif key == "_aspect":
                    continue
                else:
                    converted_children = convert_to_gui_format(child)
                    if "_aspect" in child:
                        gui_node.append({
                            'id': str(key),
                            'description': get_aspect_gui_description(child["_aspect"]),
                            'children': converted_children or []
                        })
                    else:
                        gui_node.append({
                            'id': str(key),
                            'children': converted_children or []
                        })
            return gui_node

        tree_data = convert_to_gui_format(raw_tree)
        return tree_data or []

    def save_to_db(self) -> None:
        raise NotImplementedError("Save on DB not implemented yet")

    def get_stats(self) -> dict[str, Any]:
        """
        Returns statistics about the current state of the Manager.
        Returns:
            dict[str, Any]: A dictionary containing statistics such as number of objects and connections.
        """
        base_stats = {
            "num_xtargets": len(self.god.xtargets),
            "num_connections": len(self.god.connections),
            "num_attributes": len(self.god.attributes),
            "num_links": len(self.god.links),
            "num_pins": len(self.god.pins),
            "num_aspects": len(self.god.aspects)
        }

        # Add processing state info
        processing_info = self.get_processing_state()
        base_stats.update({
            "processing_state": processing_info["state"],
            "processing_progress": processing_info["progress"]
        })

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

    def get_target_pages_by_guid(self, guid: str):
        if not guid:
            return None

        if guid not in self.god.xtargets:
            return None

        target = self.god.xtargets[guid]
        pages = self.god.get_pages_of_object(target)

        return {
            "target": target,
            "pages": pages
        }

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
        """Check if there is any extracted data."""
        return len(self.god.xtargets) > 0


if __name__ == "__main__":
    logging.basicConfig(
        filename="myapp.log", encoding="utf-8", filemode="w", level=logging.INFO
    )
    manager = Manager.from_config_files("../../config.json", "../../extraction_settings.json")
    manager.process_pdfs("../../pdfs/sample.pdf")
    print(manager.get_tree())

    stats = manager.get_stats()
    print(stats)
