from .aspects_menu import load_aspects, make_config_opener
from indu_doc.manager import Manager
from indu_doc.configs import AspectsConfig


import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize with empty uploaded PDFs list
uploaded_pdfs: list[str] = []

# Load aspects and create a config opener to open the live dialog when requested
aspects = load_aspects()
logger.debug(f"Loaded aspects: {aspects}")
config_dialog_handler = make_config_opener(aspects)

# Initialize manager with current aspects configuration
aspects_config = AspectsConfig.init_from_list([
    {"Aspect": aspect.Aspect, "Separator": aspect.Separator}
    for aspect in aspects
])
manager = Manager(aspects_config)
