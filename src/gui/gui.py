from nicegui import ui
from typing import List, Dict, Any
from .aspects_menu import load_aspects, make_config_opener
from .ui_components import create_main_content
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_gui():
    """Create the main graphical user interface."""
    # Initialize with empty uploaded PDFs list
    uploaded_pdfs = []
    tree_data = [
        {'id': 'A', 'children': [{'id': 'A1'}, {'id': 'A2'}]},
        {'id': 'B', 'children': [{'id': 'B1'}, {'id': 'B2'}]},
    ]

    # Load aspects and create a config opener to open the live dialog when requested
    aspects = load_aspects()
    logger.debug(f"Loaded aspects: {aspects}")
    config_dialog_handler = make_config_opener(aspects)

    # Create main view
    with ui.card().classes('w-[950px] no-shadow border-[1px] border-gray-300'):
        ui.label('Home View').classes(
            'p-2 text-xl font-semibold bg-gray-100 w-full text-center')
        create_main_content(uploaded_pdfs, tree_data, config_dialog_handler)


def main():
    """Entry point for running the GUI application."""
    create_gui()
    ui.run()


if __name__ in {"__main__", "__mp_main__"}:
    main()
