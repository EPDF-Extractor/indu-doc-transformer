from typing import Callable
from nicegui import ui

from gui.global_state import manager


def create_primary_action_buttons(config_dialog, extract_callback: Callable, progress_callback: Callable):
    """Create the primary action buttons section."""

    with ui.column().classes('gap-2 min-w-48'):
        ui.button('Configuration', on_click=config_dialog.open).classes('w-full')
        ui.button('Extract', color='positive',
                  on_click=lambda: extract_callback(progress_callback)).classes('w-full')


def tree_page_callback():
    ui.navigate.to("/tree", new_tab=True)


def create_secondary_action_buttons():
    """Create the secondary action buttons section (row of square icon+text buttons)."""
    with ui.row().classes('w-full justify-center gap-4 py-2'):
        actions = [
            ('View Tree', 'account_tree', tree_page_callback),
            ('Search Objects', 'search', None),
            ('Export to AML', 'ios_share', None),
        ]
        for label, icon, handler in actions:
            with ui.button(on_click=handler, color='primary').props('flat').classes(
                    'w-28 h-28 flex flex-col items-center justify-center gap-1').bind_enabled(manager, 'has_data'):
                ui.icon(icon).classes('text-3xl')
                # binds the last created button
                ui.label(label).classes('text-xs font-medium')


def create_top_section(config_dialog, extract_callback: Callable, progress_callback: Callable):
    """Create the top section with PDF list and primary action buttons."""
    from . import pdf_handler
    with ui.row().classes('w-full p-4 gap-8'):
        pdf_list_container = pdf_handler.create_pdf_picker()
        create_primary_action_buttons(
            config_dialog, extract_callback, progress_callback)
    return pdf_list_container


def create_bottom_section():
    """Create the bottom section with secondary action buttons."""
    with ui.row().classes('w-full p-4 gap-8'):
        create_secondary_action_buttons()


def create_main_content(config_dialog, extract_callback: Callable, progress_callback: Callable):
    """Create the main content area with top and bottom sections."""
    with ui.column().classes('w-full'):
        create_top_section(config_dialog, extract_callback, progress_callback)
        ui.separator()
        create_bottom_section()
