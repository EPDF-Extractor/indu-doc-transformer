from typing import List, Any

from pymupdf import pymupdf
from tqdm import tqdm
import logging

from .common_page_utils import detect_page_type
from .configs import AspectsConfig
from .god import God
from .page_processor import PageProcessor
from .xtarget import XTarget

logger = logging.getLogger(__name__)


class Manager:
    def __init__(self, config_path) -> None:
        self.config_path = config_path
        try:
            self.configs = AspectsConfig.init_from_file(config_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load config from {config_path}: {e}")

        self.god = God(self.configs)
        self.page_processor = PageProcessor(self.god)

    def process_pdf(self, pdf_path: str) -> None:
        doc = pymupdf.open(pdf_path)
        for page in tqdm(doc):  # type: ignore
            logger.info(f"Processing page {page.number + 1}")
            page_type = detect_page_type(page)
            if page_type is not None:
                self.page_processor.run(page, page_type)
            else:
                logger.info(
                    f"Could not detect page type for page #{page.number + 1}")

    def update_configs(self, configs: AspectsConfig) -> None:
        raise NotImplementedError(
            "Update configs not implemented yet, It might be tricky"
        )

    def get_tree(self) -> Any:
        # form tree of objects by aspects. Level of the tree is aspect priority
        raise NotImplementedError("Tree view not implemented yet")

    def save_to_db(self) -> None:
        raise NotImplementedError("Save on DB not implemented yet")

    def get_stats(self) -> dict[str, Any]:
        """
        Returns statistics about the current state of the Manager.
        Returns:
            dict[str, Any]: A dictionary containing statistics such as number of objects and connections.
        """
        return {
            "num_xtargets": len(self.god.xtargets),
            "num_connections": len(self.god.connections),
            "num_attributes": len(self.god.attributes),
            "num_links": len(self.god.links),
            "num_pins": len(self.god.pins),
        }

    def get_xtargets(self) -> List[XTarget]:
        return list(self.god.xtargets)

    def get_connections(self) -> List:
        return list(self.god.connections)

    def get_attributes(self) -> List:
        return list(self.god.attributes)

    def get_links(self) -> List:
        return list(self.god.links)

    def get_pins(self) -> List:
        return list(self.god.pins)


if __name__ == "__main__":
    logging.basicConfig(
        filename="myapp.log", encoding="utf-8", filemode="w", level=logging.INFO
    )
    manager = Manager("config.json")
    manager.process_pdf("pdfs/sample.pdf")
    stats = manager.get_stats()
    print(stats)
