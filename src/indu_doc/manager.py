from typing import Any
import threading
from enum import Enum

from pymupdf import pymupdf
from tqdm import tqdm
import logging

from indu_doc.common_page_utils import detect_page_type
from indu_doc.configs import AspectsConfig
from indu_doc.god import God
from indu_doc.page_processor import PageProcessor
from indu_doc.tag import Tag
from indu_doc.xtarget import XTarget

logger = logging.getLogger(__name__)

class ProcessingState(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    STOPPING = "stopping"
    ERROR = "error"

class Manager:
    def __init__(self, configs: AspectsConfig) -> None:
        self.configs: AspectsConfig = configs
        self.god: God = God(self.configs)
        self.page_processor: PageProcessor = PageProcessor(self.god)

        # Threading and state management
        self._processing_thread = None
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
    def from_config_file(cls, config_path: str) -> "Manager":
        configs = AspectsConfig.init_from_file(config_path)
        return cls(configs)

    def process_pdfs(self, pdf_paths: str | list[str]) -> None:
        """
        Start PDF processing in a separate thread.
        Returns immediately, use get_processing_state() to monitor progress.
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

        self._processing_thread = threading.Thread(
            target=self._process_pdfs_worker,
            args=(pdf_paths,),
            daemon=True
        )
        self._processing_thread.start()

    def _process_pdfs_worker(self, pdf_paths: str | list[str]) -> None:
        """Worker method that runs in a separate thread."""
        try:
            if isinstance(pdf_paths, list):
                docs = [pymupdf.open(p) for p in pdf_paths]
                file_paths = pdf_paths
            else:
                docs = [pymupdf.open(pdf_paths)]
                file_paths = [pdf_paths]

            # Calculate total pages
            total_pages = sum(len(doc) for doc in docs)
            self._progress_info["total_pages"] = total_pages

            current_page = 0

            for doc, file_path in zip(docs, file_paths):
                if self._stop_event.is_set():
                    break

                self._progress_info["current_file"] = file_path
                logger.info(f"Processing file: {file_path}")

                for page in doc:
                    if self._stop_event.is_set():
                        break

                    current_page += 1
                    self._progress_info["current_page"] = current_page

                    logger.info(f"Processing page {page.number + 1}")
                    page_type = detect_page_type(page)
                    if page_type:
                        self.page_processor.run(page, page_type)
                    else:
                        logger.info(
                            f"Could not detect page type for page #{page.number + 1}")

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

            return {
                "state": self._processing_state.value,
                "progress": {
                    "current_page": self._progress_info["current_page"],
                    "total_pages": self._progress_info["total_pages"],
                    "current_file": self._progress_info["current_file"],
                    "percentage": (
                        (self._progress_info["current_page"] /
                         self._progress_info["total_pages"])
                        if self._progress_info["total_pages"] > 0 else 0
                    )
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
        self.page_processor = PageProcessor(self.god)

    def get_tree(self) -> Any:
        # form tree of objects by aspects. Level of the tree is aspect priority
        tags_parts = [(t, t.tag.get_tag_parts())
                      for t in self.god.xtargets.values()]
        # convert the parts into a prefex tree structure
        """
        tree_data = [
        {'id': 'A', 'children': [{'id': 'A1'}, {'id': 'A2', 'description': 't.tag.tag_str'}]},
        {'id': 'B', 'children': [{'id': 'B1'}, {'id': 'B2', 'description': 't.tag.tag_str'}]},
        ]
        """
        raw_tree = {}
        for t, parts in tags_parts:
            current_level = raw_tree
            for sep in self.configs.separators:
                if sep in parts:
                    TreeKey = sep + parts[sep]
                    if TreeKey not in current_level:
                        current_level[TreeKey] = {}
                    current_level = current_level[TreeKey]

            # at the leaf, we can store the full tag string or other info
            if "_targets" not in current_level:
                current_level["_targets"] = []
            if t.tag.tag_str not in current_level["_targets"]:
                current_level["_targets"].append(t)

        # convert raw_tree to the desired format for the GUI
        def get_gui_description(target: XTarget) -> str:
            lines = []
            lines.append(f"{target.tag.tag_str}")
            # lines.append(f"Type: {target.target_type.value}")
            for attr in target.attributes:
                lines.append(f" - {attr}")
            return "\n".join(lines).strip()

        def convert_to_gui_format(node):
            if not isinstance(node, dict):
                return []

            gui_node = []
            sorted_keys = sorted(
                node.keys(), key=lambda k: (k != "_targets", k))
            for key in sorted_keys:
                child = node[key]
                if key == "_targets":
                    if isinstance(child, list):
                        for target in child:
                            if isinstance(target, XTarget):
                                gui_node.append(
                                    {'id': str(target.target_type.value.upper() + " : " + target.tag.tag_str), 'description': get_gui_description(target), 'children': []})
                else:
                    converted_children = convert_to_gui_format(child)
                    gui_node.append({
                        'id': str(key),
                        'children': converted_children if converted_children else []
                    })
            return gui_node

        tree_data = convert_to_gui_format(raw_tree)
        return tree_data if tree_data else []

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

    @property
    def has_data(self) -> bool:
        """Check if there is any extracted data."""
        return len(self.god.xtargets) > 0


if __name__ == "__main__":
    logging.basicConfig(
        filename="myapp.log", encoding="utf-8", filemode="w", level=logging.INFO
    )
    manager = Manager.from_config_file("../../config.json")
    manager.process_pdfs("../../pdfs/sample.pdf")
    print(manager.get_tree())

    stats = manager.get_stats()
    print(stats)
