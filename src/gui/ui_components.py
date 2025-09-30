from typing import Callable
from nicegui import ui

from gui.global_state import manager
from indu_doc.plugin_base import AMLBuilder


def create_primary_action_buttons(config_dialog, extract_callback: Callable, progress_callback: Callable):
    """Create the primary action buttons section."""

    with ui.column().classes('gap-3 min-w-48'):
        ui.button('Configuration', on_click=config_dialog.open).classes(
            'w-full text-base font-semibold').props('outline color=blue-5')
        ui.button('Extract', color='positive',
                  on_click=lambda: extract_callback(progress_callback)).classes('w-full text-base font-semibold').props('color=green-6')


def tree_page_callback():
    ui.navigate.to("/tree", new_tab=True)


def connections_page_callback():
    ui.navigate.to("/connections", new_tab=True)


def preview_page_callback():
    ui.navigate.to("/pdf-preview?file=", new_tab=True)


def export_aml_callback():
    builder = AMLBuilder(manager.god, manager.configs)
    print("()" * 100)
    p = manager.god.links["cc308c2f-c0f5-5dfa-d344-375f1cd8fb3e"].get_guid()
    print(p)
    print(manager.god.links["cc308c2f-c0f5-5dfa-d344-375f1cd8fb3e"])
    print("()" * 100)

    aml = builder.process()
    ui.download.content(aml, 'exported_data.aml')


def create_secondary_action_buttons():
    """Create the secondary action buttons section (row of square icon+text buttons)."""
    with ui.row().classes('w-full justify-center gap-6 py-4'):
        actions = [
            ('View Tree', 'account_tree', tree_page_callback),
            ('View Connections', 'cable', connections_page_callback),
            ('View Uploaded Files', 'feed', preview_page_callback),
            ('Export to AML', 'ios_share', export_aml_callback),
        ]
        for label, icon, handler in actions:
            with ui.button(on_click=handler, color='primary').props('flat').classes(
                    'w-32 h-32 flex flex-col items-center justify-center gap-2 border-2 border-gray-600 hover:border-blue-500 hover:bg-gray-700 transition-all').bind_enabled(manager, 'has_data'):
                ui.icon(icon).classes('text-4xl text-blue-400')
                ui.separator().classes('w-full border-t visible md:invisible')
                ui.label(label).classes('text-sm font-semibold text-gray-200')


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
