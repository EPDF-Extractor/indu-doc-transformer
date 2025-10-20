from dataclasses import dataclass

from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
from .aspects_menu import load_default_aspects, make_config_opener
from indu_doc.manager import Manager
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin import EplanPDFPlugin
from .aspects_menu import load_default_aspects
from indu_doc.manager import Manager
from indu_doc.configs import AspectsConfig, LevelConfig
import pymupdf 
from typing import Optional

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize with empty uploaded PDFs list
# uploaded_pdfs: list[str] = []

# Load aspects and create a config opener to open the live dialog when requested
# aspects = load_default_aspects()

# Initialize manager with current aspects configuration
# aspects_config = AspectsConfig.init_from_list([
#     {"Aspect": aspect.Aspect, "Separator": aspect.Separator}
#     for aspect in aspects
# ])

# manager_global: Manager | None = None  # inialized inside index page builder


class ClientState:
    def __init__(self) -> None:
        self.uploaded_pdfs: list[str] = []
        self.aspects: list[LevelConfig] = load_default_aspects()
        logger.debug(f"Loaded aspects: {self.aspects}")
        ps = PageSettings(os.path.join(os.getcwd(), "page_settings.json"))
        cs = AspectsConfig.init_from_list([
            {"Aspect": aspect.Aspect, "Separator": aspect.Separator}
            for aspect in self.aspects
        ])
        pdfPlugin = EplanPDFPlugin(cs, ps)
        self.manager: Manager = Manager(cs)
        self.manager.register_plugin(pdfPlugin)
        self.current_doc: Optional[pymupdf.Document] = None  # To cache the opened PDF document
        self.current_file_path: str = ''  # To track the current file

    def is_valid(self) -> bool:
        return self.manager is not None and isinstance(self.uploaded_pdfs, list) and isinstance(self.aspects, list)


# Mapping from client ID to its state, saves session-specific data
clients_to_state: dict[str, ClientState] = {}
