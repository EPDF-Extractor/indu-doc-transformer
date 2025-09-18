from typing import List, Dict, Any
from nicegui import ui


def create_primary_action_buttons(config_dialog, uploaded_pdfs: List[str]):
    """Create the primary action buttons section."""
    with ui.column().classes('gap-2 min-w-48'):
        ui.button('Configuration', on_click=config_dialog.open).classes('w-full')
        ui.button('Extract', color='positive').classes('w-full')


def create_tree_outline(tree_data: List[Dict[str, Any]]):
    """Create the tree outline section."""
    with ui.card().classes('flex-grow h-64'):
        with ui.card_section():
            ui.label('Tree Outline').classes('text-center w-full')
        ui.separator()
        with ui.card_section().classes('overflow-auto max-h-48 w-full p-0'):
            ui.tree(
                tree_data,
                label_key='id',
                on_select=lambda e: ui.notify(f'Selected: {e.value}')
            )


def create_secondary_action_buttons():
    """Create the secondary action buttons section."""
    with ui.column().classes('gap-2 min-w-48'):
        ui.button('Search Objects').classes('w-full')
        ui.button('Export to AML').classes('w-full')


def create_top_section(uploaded_pdfs: List[str], config_dialog):
    """Create the top section with PDF list and primary action buttons."""
    from . import pdf_handler
    with ui.row().classes('w-full p-4 gap-8'):
        pdf_list_container = pdf_handler.create_pdf_picker(uploaded_pdfs)
        create_primary_action_buttons(
            config_dialog, uploaded_pdfs)
    return pdf_list_container


def create_bottom_section(tree_data: List[Dict[str, Any]]):
    """Create the bottom section with tree outline and secondary action buttons."""
    with ui.row().classes('w-full p-4 gap-8'):
        create_tree_outline(tree_data)
        create_secondary_action_buttons()


def create_main_content(uploaded_pdfs: List[str], tree_data: List[Dict[str, Any]], config_dialog):
    """Create the main content area with top and bottom sections."""
    with ui.column().classes('w-full'):
        create_top_section(uploaded_pdfs, config_dialog)
        ui.separator()
        create_bottom_section(tree_data)
