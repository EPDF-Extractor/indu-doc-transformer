from nicegui import ui
from typing import Any, Set
from indu_doc.attributes import PDFLocationAttribute
from indu_doc.god import PageMapperEntry


def create_section_header(icon: str, title: str):
    """Create a consistent section header with icon."""
    with ui.row().classes('items-center gap-2 mb-2'):
        ui.icon(icon).classes('text-blue-400 text-xl')
        ui.label(title).classes('font-semibold text-lg text-white')


def create_info_card(label: str, value: str, classes: str = 'text-sm'):
    """Create a card displaying label and value."""
    ui.label(f'{label}:').classes('font-semibold text-sm text-gray-300')
    with ui.card().classes('w-full bg-gray-700 border border-gray-600 p-3 mb-3'):
        ui.label(value).classes(f'{classes} break-all text-gray-100')


def create_type_badge(type_value: str):
    """Create a type badge with icon."""
    with ui.row().classes('items-center gap-2 mb-4'):
        ui.icon('label').classes('text-blue-400 text-xl')
        with ui.element('div').classes('inline-block bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg'):
            ui.label(type_value.upper()).classes('text-sm font-bold')


def create_attributes_section(attributes: Set[Any]):
    """Create an attributes section with cards."""
    if not attributes:
        return

    ui.separator().classes('my-4 bg-gray-600')
    create_section_header('settings', 'Attributes')
    with ui.column().classes('gap-2 ml-6'):
        for attr in attributes:
            if attr is None or isinstance(attr, PDFLocationAttribute):
                continue
            with ui.card().classes('w-full bg-gray-700 border border-gray-600 p-3'):
                ui.label(f'{attr}').classes('text-sm text-gray-200')


def create_occurrences_section(pages: Set[PageMapperEntry]):
    """Create an occurrences section with clickable cards."""
    if not pages:
        return

    ui.separator().classes('my-4 bg-gray-600')
    create_section_header('description', f'Occurrences ({len(pages)})')
    with ui.column().classes('gap-2 ml-6'):
        for page in sorted(pages, key=lambda p: (p.file_path, p.page_number)):
            file_name = page.file_path.split('\\')[-1]

            def navigate_to_page(file_path: str, page_num: int):
                ui.navigate.to(
                    f'/pdf-preview?file={file_path}&page={page_num}', new_tab=True)

            with ui.card().classes('w-full bg-gray-700 border border-gray-600 p-3 hover:bg-gray-600 hover:border-blue-500 cursor-pointer transition-all').on(
                'click', lambda p=page: navigate_to_page(
                    p.file_path, p.page_number)
            ):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('insert_drive_file').classes('text-blue-400')
                    ui.label(f'Page {page.page_number}').classes(
                        'text-sm font-semibold text-white')
                ui.label(file_name).classes('text-xs text-gray-400 ml-6')


def create_empty_state(message: str = 'Select an item to view details'):
    """Create an empty state message."""
    ui.label(message).classes('text-gray-400 text-center text-lg')


def create_collapsible_section(icon: str, title: str, default_open: bool = True):
    """Create a collapsible section with icon and title."""
    expansion = ui.expansion(title, icon=icon, value=default_open).classes(
        'w-full bg-gray-700 border border-gray-600 text-white mb-3'
    )
    return expansion
