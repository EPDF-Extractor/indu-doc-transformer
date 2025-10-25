from nicegui import ui
from typing import List, Dict, Any
from gui.global_state import ClientState
from indu_doc.connection import Connection, Link
from indu_doc.searcher import Searcher
from indu_doc.attributes import PDFLocationAttribute
from gui.detail_panel_components import (create_info_card, 
    create_empty_state, create_collapsible_section
)


def filter_connections_by_searcher(connections: List[Connection], searcher: Searcher, query: str) -> List[Connection]:
    """Filter connections using the Searcher class with query syntax."""
    if not query or not query.strip():
        return connections
    
    try:
        # Search for matching connection GUIDs
        matching_guids = searcher.search_connections(query)
        matching_guids_set = set(matching_guids)
        
        # Filter connections based on matching GUIDs
        filtered = [conn for conn in connections if conn.get_guid() in matching_guids_set]
        return filtered
    except Exception as e:
        # If query is invalid, show error and return empty
        ui.notify(f'Invalid query: {str(e)}', type='negative')
        return []


def _build_search_guide_nodes(tree_dict: Dict[str, Any], path: List[str] | None = None) -> List[Dict[str, Any]]:
    path = path or []
    nodes: List[Dict[str, Any]] = []
    
    # Separate direct properties from nested ones
    direct_keys = []
    nested_keys = []
    
    for key in tree_dict.keys():
        if key == '__filters__':
            continue
        value = tree_dict[key]
        # Check if this is a direct property (no nested dict children except __filters__)
        has_nested_children = any(k != '__filters__' and isinstance(v, dict) for k, v in value.items())
        if has_nested_children:
            nested_keys.append(key)
        else:
            direct_keys.append(key)
    
    # Sort within each group
    direct_keys.sort(key=str.lower)
    nested_keys.sort(key=str.lower)
    
    # Process direct keys first, then nested keys
    for key in direct_keys + nested_keys:
        value = tree_dict[key]
        next_path = path if key == '[list items]' else path + [key]
        children = _build_search_guide_nodes(value, next_path)
        
        # Special handling for list items - flatten them into the parent
        if key == '[list items]':
            # Instead of creating a node for '[list items]', return its children directly
            nodes.extend(children)
            continue
            
        filters_source = value.get('__filters__')
        filters = sorted(filters_source, key=str.lower) if filters_source else []
        if key == '[list items]' and not children and filters_source:
            children = []
        description = ''
        if filters:
            description = '<div class="guide-templates">' + ''.join(
                f'<div><code>{tmpl}</code></div>' for tmpl in filters
            ) + '</div>'
        node = {'id': key, 'children': children}
        if description:
            node['description'] = description
            node['body'] = description
        nodes.append(node)
    return nodes


def create_connection_list(connections: List[Connection], details_callback, state: ClientState, searcher: Searcher):
    """Create a filterable list of all connections."""

    ui.label('Connections').classes(
        'text-center w-full text-xl font-semibold mb-2 text-white')
    ui.label(f'Total connections: {len(connections)}').classes(
        'text-center w-full text-sm text-gray-300 mb-4')

    filter_input = ui.input('Search query (e.g., @tag=E+A1 @src=INPUT)').classes(
        'w-full mb-4').props('dark outlined')

    guide_dialog = ui.dialog()

    with guide_dialog, ui.card().classes('bg-gray-900 border border-gray-700 text-white w-[60rem] max-h-[70rem] overflow-hidden'):
        ui.label('Searchable Fields Guide').classes('text-lg font-semibold mb-2')
        ui.label('Tree of available keys for advanced queries.').classes('text-xs text-gray-400 mb-3')
        guide_tree_container = ui.column().classes('w-full max-h-[60rem] overflow-y-auto')

    def show_search_guide():
        guide_tree_container.clear()
        guide_structure = searcher.create_connection_search_guide_tree()
        guide_nodes = _build_search_guide_nodes(guide_structure)
        with guide_tree_container:
            if guide_nodes:
                guide_tree = ui.tree(guide_nodes, label_key='id').props('dark no-transition').classes('text-white')
                guide_tree.expand()
                guide_tree.add_slot('default-body', '''
                    <div v-if="props.node.description" v-html="props.node.description" @click="handleCodeClick"></div>
                ''')
            else:
                ui.label('Guide unavailable. Index connections first.').classes('text-sm text-gray-400')
        
        # Add the click handler function to Vue global properties
        ui.run_javascript('''
            app.config.globalProperties.handleCodeClick = function(event) {
                if (event.target.tagName === "CODE") {
                    const text = event.target.textContent;
                    navigator.clipboard.writeText(text).then(() => {
                        // Show a brief success indication
                        const originalBg = event.target.style.backgroundColor;
                        event.target.style.backgroundColor = "#10b981";
                        setTimeout(() => {
                            event.target.style.backgroundColor = originalBg;
                        }, 200);
                    }).catch(err => {
                        console.error("Failed to copy: ", err);
                    });
                }
            }
        ''')
        
        guide_dialog.open()

    ui.button('Show Search Guide', on_click=show_search_guide).classes('self-start mb-2').props('color=primary outline')
    
    # Add help text for query syntax
    with ui.row().classes('w-full mb-2 gap-2'):
        ui.icon('info').classes('text-blue-400')
        ui.label('Examples: tag pattern, @guid=xxx, @src=INPUT, @dest=OUTPUT, @links.srcpin=43').classes('text-xs text-gray-400')

    # Add custom CSS for tree description styling
    ui.add_head_html('''
    <style>
        .guide-templates div {
            margin-bottom: 4px;
        }
        .guide-templates code {
            background-color: #312e81;
            color: #dbeafe;
            padding: 2px 6px;
            border-radius: 4px;
            display: inline-block;
            font-size: 0.85em;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .guide-templates code:hover {
            background-color: #1e1b4b;
        }
    </style>
    ''')

    # Container for connection list
    with ui.element('div').classes('flex-1 overflow-auto border-2 border-gray-600 rounded-lg p-3 w-full bg-gray-900'):
        list_container = ui.column().classes('w-full gap-2')

        def render_connections(filter_str: str = ''):
            """Render the filtered connection list."""
            list_container.clear()

            # Filter connections using searcher
            filtered = filter_connections_by_searcher(connections, searcher, filter_str)

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
    # Initialize searcher with indexed connections
    searcher = Searcher(state.manager.god, init_index=["conns"])
    
    with ui.card().classes('w-full h-screen no-shadow border-2 border-gray-700 bg-gray-900 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0 bg-gray-800'):
            with ui.row().classes('w-full items-center'):
                ui.label('Connections View').classes(
                    'text-2xl font-bold flex-grow text-center text-white')

        ui.separator().classes('bg-gray-700')

        # Main content with list and detail panel using splitter
        with ui.card_section().classes('flex-1 min-h-0 w-full max-w-full overflow-hidden bg-gray-900'):
            with ui.splitter(value=70).classes('w-full h-full') as splitter:
                with splitter.before:
                    # Connection list (left side)
                    list_container = ui.column().classes('h-full w-full')

                with splitter.after:
                    # Detail panel (right side)
                    detail_panel = ui.column().classes(
                        'h-full w-full border-2 border-gray-600 rounded-lg p-4 overflow-y-auto bg-gray-800')

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

                        # Source - only show if exists
                        if conn.src:
                            with create_collapsible_section('input', 'Source', default_open=True):
                                with ui.column().classes('gap-2 p-3'):
                                    create_info_card(
                                        'Tag', conn.src.tag.tag_str, 'font-mono text-sm')
                                    ui.label(f'Type: {conn.src.target_type.value}').classes(
                                        'text-sm text-gray-300')

                        # Destination - only show if exists
                        if conn.dest:
                            with create_collapsible_section('output', 'Destination', default_open=True):
                                with ui.column().classes('gap-2 p-3'):
                                    create_info_card(
                                        'Tag', conn.dest.tag.tag_str, 'font-mono text-sm')
                                    ui.label(f'Type: {conn.dest.target_type.value}').classes(
                                        'text-sm text-gray-300')

                        # Through (cable/medium) - only show if exists
                        if conn.through:
                            with create_collapsible_section('cable', 'Through', default_open=True):
                                with ui.column().classes('gap-2 p-3'):
                                    create_info_card(
                                        'Tag', conn.through.tag.tag_str, 'font-mono text-sm')
                                    ui.label(f'Type: {conn.through.target_type.value}').classes(
                                        'text-sm text-gray-300')

                                    # Through object attributes - only if they exist
                                    if conn.through.attributes:
                                        used_attrs = [attr for attr in conn.through.attributes if not isinstance(attr, PDFLocationAttribute)]
                                        if used_attrs:
                                            ui.label('Attributes:').classes(
                                                'text-sm font-semibold mt-2 text-gray-300')
                                            with ui.column().classes('gap-1 mt-1'):
                                                for attr in used_attrs:
                                                    with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-2'):
                                                        ui.label(f'{attr}').classes(
                                                            'text-xs text-gray-200')

                        # Links - only show if exists
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
                                                # Link attributes - only if they exist
                                                if link.attributes:
                                                    used_attrs = [attr for attr in link.attributes if not isinstance(attr, PDFLocationAttribute)]
                                                    if used_attrs:
                                                        ui.label('Attributes:').classes(
                                                            'text-sm font-semibold mt-2 text-gray-300')
                                                        with ui.column().classes('gap-1 mt-1'):
                                                            for attr in used_attrs:
                                                                with ui.card().classes('w-full bg-gray-500 border border-gray-400 p-2'):
                                                                    ui.label(f'{attr}').classes(
                                                                        'text-xs text-gray-200')

                        # GUID - always show
                        with create_collapsible_section('fingerprint', 'GUID', default_open=False):
                            with ui.column().classes('p-3'):
                                with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-3'):
                                    ui.label(conn.get_guid()).classes(
                                        'font-mono text-xs break-all text-gray-100')

                        # Occurrences - only show if there are pages
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
                            connections, update_detail_panel, state, searcher)

                # Initial load
                refresh_connections()
