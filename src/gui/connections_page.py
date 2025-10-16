from nicegui import ui
from typing import List, Dict, Any
from gui.global_state import ClientState
from indu_doc.connection import Connection, Link
from gui.detail_panel_components import (
    create_section_header, create_info_card, create_occurrences_section,
    create_empty_state, create_collapsible_section
)


def create_connection_list(connections: List[Connection], details_callback, state: ClientState):
    """Create a filterable list of all connections."""

    ui.label('Connections').classes(
        'text-center w-full text-xl font-semibold mb-2 text-white')
    ui.label(f'Total connections: {len(connections)}').classes(
        'text-center w-full text-sm text-gray-300 mb-4')

    filter_input = ui.input('Filter connections...').classes(
        'w-full mb-4').props('dark outlined')

    # Container for connection list
    with ui.element('div').classes('flex-1 overflow-auto border-2 border-gray-600 rounded-lg p-3 w-full bg-gray-900'):
        list_container = ui.column().classes('w-full gap-2')

        def render_connections(filter_str: str = ''):
            """Render the filtered connection list."""
            list_container.clear()

            # Filter connections
            filtered = connections
            if filter_str:
                filter_lower = filter_str.lower()
                filtered = [
                    conn for conn in connections
                    if (conn.src and filter_lower in conn.src.tag.tag_str.lower()) or
                       (conn.dest and filter_lower in conn.dest.tag.tag_str.lower()) or
                       (conn.through and filter_lower in conn.through.tag.tag_str.lower())
                ]

            if not filtered:
                with list_container:
                    ui.label('No connections found').classes(
                        'text-center text-gray-400 mt-4')
                return

            # Render each connection as a card
            with list_container:
                for conn in filtered:
                    src_tag = conn.src.tag.tag_str if conn.src else 'N/A'
                    dest_tag = conn.dest.tag.tag_str if conn.dest else 'N/A'
                    through_tag = conn.through.tag.tag_str if conn.through else 'Direct'

                    with ui.card().classes('w-full cursor-pointer hover:bg-gray-700 bg-gray-800 border border-gray-600 transition-colors').on('click', lambda c=conn: handle_click(c)):
                        with ui.row().classes('w-full items-center gap-4 p-2'):
                            ui.icon('arrow_forward').classes(
                                'text-3xl text-blue-400')
                            with ui.column().classes('flex-1'):
                                ui.label(f'{src_tag} → {dest_tag}').classes(
                                    'font-semibold text-white')
                                ui.label(f'Via: {through_tag}').classes(
                                    'text-sm text-gray-300')
                                if conn.links:
                                    ui.label(f'{len(conn.links)} link(s)').classes(
                                        'text-xs text-gray-400')

        def handle_click(conn: Connection):
            """Handle connection click."""
            conn_info = state.manager.get_connection_details(
                conn.get_guid())
            if conn_info:
                details_callback(conn_info)

        filter_input.on_value_change(lambda e: render_connections(e.value))

        # Initial render
        render_connections()


def create_connections_page(state: ClientState):
    """Create a dedicated page for exploring connections."""
    with ui.card().classes('w-full h-screen no-shadow border-2 border-gray-700 bg-gray-900 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0 bg-gray-800'):
            with ui.row().classes('w-full items-center'):
                ui.label('Connections View').classes(
                    'text-2xl font-bold flex-grow text-center text-white')

        ui.separator().classes('bg-gray-700')

        # Main content with list and detail panel
        with ui.card_section().classes('flex-1 min-h-0 w-full max-w-full overflow-hidden bg-gray-900'):
            with ui.row().classes('w-full h-full gap-4'):
                # Connection list (left side)
                list_container = ui.column().classes('flex-1 min-w-0 h-full')

                # Detail panel (right side)
                detail_panel = ui.column().classes(
                    'w-96 flex-shrink-0 h-full border-2 border-gray-600 rounded-lg p-4 overflow-y-auto bg-gray-800')

                with detail_panel:
                    create_empty_state('Select a connection to view details')

                def update_detail_panel(conn_info: Dict[str, Any]):
                    """Update the detail panel with connection details."""
                    detail_panel.clear()

                    conn: Connection = conn_info['connection']
                    pages = conn_info.get('pages', set())

                    with detail_panel:
                        ui.label('Connection Details').classes(
                            'text-xl font-bold mb-4 text-white')

                        # Source
                        with create_collapsible_section('input', 'Source', default_open=True):
                            if conn.src:
                                with ui.column().classes('gap-2 p-3'):
                                    create_info_card(
                                        'Tag', conn.src.tag.tag_str, 'font-mono text-sm')
                                    ui.label(f'Type: {conn.src.target_type.value}').classes(
                                        'text-sm text-gray-300')
                            else:
                                ui.label(
                                    'N/A').classes('text-sm text-gray-400 p-3')

                        # Destination
                        with create_collapsible_section('output', 'Destination', default_open=True):
                            if conn.dest:
                                with ui.column().classes('gap-2 p-3'):
                                    create_info_card(
                                        'Tag', conn.dest.tag.tag_str, 'font-mono text-sm')
                                    ui.label(f'Type: {conn.dest.target_type.value}').classes(
                                        'text-sm text-gray-300')
                            else:
                                ui.label(
                                    'N/A').classes('text-sm text-gray-400 p-3')

                        # Through (cable/medium)
                        with create_collapsible_section('cable', 'Through', default_open=True):
                            if conn.through:
                                with ui.column().classes('gap-2 p-3'):
                                    create_info_card(
                                        'Tag', conn.through.tag.tag_str, 'font-mono text-sm')
                                    ui.label(f'Type: {conn.through.target_type.value}').classes(
                                        'text-sm text-gray-300')

                                    # Through object attributes
                                    if conn.through.attributes:
                                        ui.label('Attributes:').classes(
                                            'text-sm font-semibold mt-2 text-gray-300')
                                        with ui.column().classes('gap-1 mt-1'):
                                            for attr in conn.through.attributes:
                                                with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-2'):
                                                    ui.label(f'{attr}').classes(
                                                        'text-xs text-gray-200')
                            else:
                                ui.label('Direct connection').classes(
                                    'text-sm text-gray-400 p-3')

                        # Links
                        if conn.links:
                            with create_collapsible_section('link', f'Links ({len(conn.links)})', default_open=True):
                                with ui.column().classes('gap-2 p-3'):
                                    for i, link in enumerate(conn.links, 1):
                                        with ui.expansion(f'Link {i}: {link.name}', icon='link').classes('w-full bg-gray-600 border border-gray-500 text-white'):
                                            with ui.column().classes('gap-2 p-2'):
                                                if link.src_pin:
                                                    ui.label(f'Source Pin: {link.src_pin.name}').classes(
                                                        'text-sm font-mono text-gray-200')
                                                    ui.label(f'GUID: {link.src_pin.get_guid()}').classes(
                                                        'text-xs text-gray-400')
                                                if link.dest_pin:
                                                    ui.label(f'Dest Pin: {link.dest_pin.name}').classes(
                                                        'text-sm font-mono text-gray-200')
                                                    ui.label(f'GUID: {link.dest_pin.get_guid()}').classes(
                                                        'text-xs text-gray-400')
                                                if link.get_guid():
                                                    ui.label(f'GUID: {link.get_guid()}').classes(
                                                        'text-xs text-gray-400')
                                                # Link attributes
                                                if link.attributes:
                                                    ui.label('Attributes:').classes(
                                                        'text-sm font-semibold mt-2 text-gray-300')
                                                    with ui.column().classes('gap-1 mt-1'):
                                                        for attr in link.attributes:
                                                            with ui.card().classes('w-full bg-gray-500 border border-gray-400 p-2'):
                                                                ui.label(f'{attr}').classes(
                                                                    'text-xs text-gray-200')

                        # GUID
                        with create_collapsible_section('fingerprint', 'GUID', default_open=False):
                            with ui.column().classes('p-3'):
                                with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-3'):
                                    ui.label(conn.get_guid()).classes(
                                        'font-mono text-xs break-all text-gray-100')

                        # Occurrences
                        if pages:
                            with create_collapsible_section('description', f'Occurrences ({len(pages)})', default_open=False):
                                with ui.column().classes('gap-2 p-3'):
                                    for page in sorted(pages, key=lambda p: (p.file_path, p.page_number)):
                                        file_name = page.file_path.split(
                                            '\\')[-1]

                                        def navigate_to_page(file_path: str, page_num: int):
                                            ui.navigate.to(
                                                f'/pdf-preview?file={file_path}&page={page_num}', new_tab=True)

                                        with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-3 hover:bg-gray-500 hover:border-blue-500 cursor-pointer transition-all').on(
                                            'click', lambda p=page: navigate_to_page(
                                                p.file_path, p.page_number)
                                        ):
                                            with ui.row().classes('items-center gap-2'):
                                                ui.icon('insert_drive_file').classes(
                                                    'text-blue-400')
                                                ui.label(f'Page {page.page_number}').classes(
                                                    'text-sm font-semibold text-white')
                                            ui.label(file_name).classes(
                                                'text-xs text-gray-400 ml-6')

                def refresh_connections():
                    """Refresh the connections list."""
                    connections = state.manager.get_connections()
                    list_container.clear()
                    with list_container:
                        create_connection_list(
                            connections, update_detail_panel, state)

                # Initial load
                refresh_connections()
