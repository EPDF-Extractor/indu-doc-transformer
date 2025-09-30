from nicegui import ui
from typing import List, Dict, Any
from indu_doc.connection import Connection, Link
from gui.global_state import manager
from gui.detail_panel_components import (
    create_section_header, create_info_card, create_occurrences_section,
    create_empty_state
)


def create_connection_list(connections: List[Connection], details_callback):
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
            conn_info = manager.get_connection_details(conn.get_guid())
            if conn_info:
                details_callback(conn_info)

        filter_input.on_value_change(lambda e: render_connections(e.value))

        # Initial render
        render_connections()


def create_connections_page():
    """Create a dedicated page for exploring connections."""

    with ui.card().classes('w-full h-screen no-shadow border-2 border-gray-700 bg-gray-900 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0 bg-gray-800'):
            with ui.row().classes('w-full items-center'):
                ui.label('Connections View').classes(
                    'text-2xl font-bold flex-grow text-center text-white')
                ui.button('Refresh', on_click=lambda: refresh_connections()).classes(
                    'ml-4').props('outline color=blue-5')

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
                        ui.separator().classes('my-2 bg-gray-600')
                        create_section_header('input', 'Source')
                        if conn.src:
                            with ui.column().classes('ml-6 gap-2'):
                                create_info_card(
                                    'Tag', conn.src.tag.tag_str, 'font-mono text-sm')
                                ui.label(f'Type: {conn.src.target_type.value}').classes(
                                    'text-sm text-gray-300')
                        else:
                            ui.label(
                                'N/A').classes('text-sm text-gray-400 ml-6')

                        # Destination
                        ui.separator().classes('my-4 bg-gray-600')
                        create_section_header('output', 'Destination')
                        if conn.dest:
                            with ui.column().classes('ml-6 gap-2'):
                                create_info_card(
                                    'Tag', conn.dest.tag.tag_str, 'font-mono text-sm')
                                ui.label(f'Type: {conn.dest.target_type.value}').classes(
                                    'text-sm text-gray-300')
                        else:
                            ui.label(
                                'N/A').classes('text-sm text-gray-400 ml-6')

                        # Through (cable/medium)
                        ui.separator().classes('my-4 bg-gray-600')
                        create_section_header('cable', 'Through')
                        if conn.through:
                            with ui.column().classes('ml-6 gap-2'):
                                create_info_card(
                                    'Tag', conn.through.tag.tag_str, 'font-mono text-sm')
                                ui.label(f'Type: {conn.through.target_type.value}').classes(
                                    'text-sm text-gray-300')

                                # Through object attributes (using common component style)
                                if conn.through.attributes:
                                    ui.label('Attributes:').classes(
                                        'text-sm font-semibold mt-2 text-gray-300')
                                    with ui.column().classes('gap-1 mt-1'):
                                        for attr in conn.through.attributes:
                                            with ui.card().classes('w-full bg-gray-700 border border-gray-600 p-2'):
                                                ui.label(f'{attr}').classes(
                                                    'text-xs text-gray-200')
                        else:
                            ui.label('Direct connection').classes(
                                'text-sm text-gray-400 ml-6')

                        # Links
                        if conn.links:
                            ui.separator().classes('my-4 bg-gray-600')
                            create_section_header(
                                'link', f'Links ({len(conn.links)})')
                            with ui.column().classes('ml-6 gap-2'):
                                for i, link in enumerate(conn.links, 1):
                                    with ui.expansion(f'Link {i}: {link.name}', icon='link').classes('w-full bg-gray-700 border border-gray-600 text-white'):
                                        with ui.column().classes('gap-2 p-2'):
                                            if link.src_pin:
                                                ui.label(f'Source Pin: {link.src_pin.name}').classes(
                                                    'text-sm font-mono text-gray-200')
                                            if link.dest_pin:
                                                ui.label(f'Dest Pin: {link.dest_pin.name}').classes(
                                                    'text-sm font-mono text-gray-200')
                                            if link.get_guid():
                                                ui.label(f'GUID: {link.get_guid()}').classes(
                                                    'text-xs text-gray-400')
                                            # Link attributes
                                            if link.attributes:
                                                ui.label('Attributes:').classes(
                                                    'text-sm font-semibold mt-2 text-gray-300')
                                                with ui.column().classes('gap-1 mt-1'):
                                                    for attr in link.attributes:
                                                        with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-2'):
                                                            ui.label(f'{attr}').classes(
                                                                'text-xs text-gray-200')

                        # GUID
                        ui.separator().classes('my-4 bg-gray-600')
                        create_info_card(
                            'GUID', conn.get_guid(), 'font-mono text-xs')

                        # Occurrences
                        create_occurrences_section(pages)

                def refresh_connections():
                    """Refresh the connections list."""
                    connections = manager.get_connections()
                    list_container.clear()
                    with list_container:
                        create_connection_list(
                            connections, update_detail_panel)

                # Initial load
                refresh_connections()
