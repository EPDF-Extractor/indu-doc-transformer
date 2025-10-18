from nicegui import ui
from typing import List, Dict, Any
from gui.global_state import ClientState
from indu_doc.god import PageMapperEntry
from indu_doc.xtarget import XTarget
from indu_doc.searcher import Searcher
from gui.detail_panel_components import (
    create_type_badge, create_info_card, create_attributes_section,
    create_occurrences_section, create_empty_state, create_collapsible_section
)


def sanitize_tree_data(tree_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recursively sanitize tree data to ensure all children arrays are properly initialized."""
    if not tree_data:
        return []

    sanitized_data = []
    for node in tree_data:
        if isinstance(node, dict):
            sanitized_node = node.copy()
            # Ensure children is always a list
            if 'children' in sanitized_node:
                if sanitized_node['children'] is None:
                    sanitized_node['children'] = []
                else:
                    sanitized_node['children'] = sanitize_tree_data(
                        sanitized_node['children'])
            else:
                sanitized_node['children'] = []
            sanitized_data.append(sanitized_node)

    return sanitized_data


# Remove the old filter_tree_by_description function and replace with searcher-based approach
def filter_tree_by_searcher(tree_data: List[Dict[str, Any]], searcher: Searcher, query: str) -> List[Dict[str, Any]]:
    """Filter tree nodes using the Searcher class with query syntax."""
    if not query or not query.strip():
        return tree_data
    
    try:
        # Search for matching target GUIDs
        matching_guids = searcher.search_targets(query)
        matching_guids_set = set(matching_guids)
        
        def filter_recursive(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            filtered = []
            for node in nodes:
                # Extract GUID from description
                desc = node.get('description', '')
                node_guid = None
                if desc:
                    import re
                    guid_match = re.search(r'<code>([^<]+)</code>', desc)
                    if guid_match:
                        node_guid = guid_match.group(1)
                
                # Check if this node matches
                node_matches = node_guid in matching_guids_set if node_guid else False
                
                # Recursively filter children
                children = node.get('children', [])
                filtered_children = filter_recursive(children) if children else []
                
                # Include node if it matches or has matching children
                if node_matches or filtered_children:
                    new_node = node.copy()
                    new_node['children'] = filtered_children
                    filtered.append(new_node)
            
            return filtered
        
        return filter_recursive(tree_data)
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


def create_tree_outline(tree_data: List[Dict[str, Any]], details_callback, state: ClientState, searcher: Searcher):
    """Create the tree outline section for the dedicated tree page with searcher-based filtering."""
    ui.label('Tree Outline').classes(
        'text-center w-full text-xl font-semibold mb-2 text-white')
    safe_tree_data = sanitize_tree_data(
        tree_data if tree_data is not None else [])
    ui.label(f'Total nodes: {len(safe_tree_data)}').classes(
        'text-center w-full text-sm text-gray-300 mb-4')

    filter_input = ui.input(
        'Search query (e.g., @tag=E+A1 @type=SYMBOL)').classes('w-full mb-4').props('dark outlined')

    guide_dialog = ui.dialog()

    with guide_dialog, ui.card().classes('bg-gray-900 border border-gray-700 text-white w-[60rem] max-h-[70rem] overflow-hidden'):
        ui.label('Searchable Fields Guide').classes('text-lg font-semibold mb-2')
        ui.label('Tree of available keys for advanced queries.').classes('text-xs text-gray-400 mb-3')
        guide_tree_container = ui.column().classes('w-full max-h-[60rem] overflow-y-auto')

    def show_search_guide():
        guide_tree_container.clear()
        guide_structure = searcher.create_target_search_guide_tree()
        guide_nodes = _build_search_guide_nodes(guide_structure)
        with guide_tree_container:
            if guide_nodes:
                guide_tree = ui.tree(guide_nodes, label_key='id').props('dark no-transition').classes('text-white')
                guide_tree.expand()
                guide_tree.add_slot('default-body', '''
                    <div v-if="props.node.description" v-html="props.node.description" @click="handleCodeClick"></div>
                ''')
            else:
                ui.label('Guide unavailable. Index targets first.').classes('text-sm text-gray-400')
        
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
        ui.label('Examples: tag pattern, @guid=xxx, @type=SYMBOL, @attributes(Length)=12m').classes('text-xs text-gray-400')

    # Add custom CSS for tree description styling
    ui.add_head_html('''
    <style>
        .tree-description {
            padding: 8px;
            font-size: 0.9em;
            line-height: 1.6;
            color: #e5e7eb;
        }
        .tree-description > div {
            margin-bottom: 6px;
        }
        .tree-description .badge {
            background-color: #3b82f6;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
        }
        .tree-description code {
            background-color: #1e40af;
            color: #bfdbfe;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 0.9em;
        }
        .tree-description ul {
            margin: 4px 0 0 20px;
            padding: 0;
        }
        .tree-description li {
            margin-bottom: 2px;
            color: #d1d5db;
        }
        .target-type, .target-tag, .target-guid {
            display: flex;
            gap: 8px;
        }
        .q-tree__node-header {
            padding: 8px;
        }
        .q-tree__node-header:hover {
            background-color: #374151 !important;
        }
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

    # Create a container for the tree that will take remaining space
    with ui.element('div').classes('flex-1 overflow-auto border-2 border-gray-600 rounded-lg p-3 w-full bg-gray-900'):
        tree_section = ui.element('div').classes('w-full')

        def handle_click(e):
            """Handle tree node click - show details in side panel."""
            # Ignore deselection events (when value is None)
            if e.value is None:
                return

            print(f"Tree node clicked: {e.value} (raw event: {e})")
            node_id = e.value if isinstance(e.value, str) else str(e.value)
            # Extract the actual tag string (remove the prefix if present)
            tag_str = node_id[node_id.find(
                ":")+1:].strip() if ":" in node_id else node_id

            # Get target details and update side panel
            target_info = state.manager.get_target_pages_by_tag(tag_str)
            if target_info:
                details_callback(target_info)

            # Also copy to clipboard
            ui.clipboard.write(tag_str)
            ui.notify(f'Copied to clipboard: {tag_str}')

        def update_tree():
            tree_section.clear()
            query = filter_input.value or ''
            filtered = filter_tree_by_searcher(safe_tree_data, searcher, query)
            if filtered and len(filtered) > 0:
                with tree_section:
                    tree = ui.tree(
                        filtered,
                        label_key='id',
                        on_select=handle_click,
                    ).props('dark selected-color=blue-5 no-transition').classes('png-tree-icon w-full text-white')
                    tree.add_slot('default-header', '''
                    <span :props="props"><strong>{{ props.node.id }}</strong></span>
                    ''')
                    tree.add_slot('default-body', '''
                        <div v-if="props.node.description" v-html="props.node.description"></div>
                    ''')
            else:
                with tree_section:
                    ui.label('No data available. Please extract PDFs first or adjust your filter.').classes(
                        'text-center text-gray-400')

        filter_input.on_value_change(lambda e: update_tree())
        # Initial render
        update_tree()


def create_tree_page(state: ClientState):
    """Create a dedicated page for displaying the tree structure."""
    # Initialize searcher with indexed targets
    searcher = Searcher(state.manager.god, init_index=["targets"])
    
    with ui.card().classes('w-full h-screen no-shadow border-2 border-gray-700 bg-gray-900 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0 bg-gray-800'):
            with ui.row().classes('w-full items-center'):
                ui.label('Tree View').classes(
                    'text-2xl font-bold flex-grow text-center text-white')

        ui.separator().classes('bg-gray-700')

        # Main content with tree and side panel
        with ui.card_section().classes('flex-1 min-h-0 w-full max-w-full overflow-hidden bg-gray-900'):
            with ui.row().classes('w-full h-full gap-4'):
                # Tree container (left side)
                tree_container = ui.column().classes(
                    'flex-1 min-w-0 h-full')

                # Side panel container (right side)
                side_panel = ui.column().classes(
                    'w-96 flex-shrink-0 h-full border-2 border-gray-600 rounded-lg p-4 overflow-y-auto bg-gray-800')

                with side_panel:
                    create_empty_state('Select a node to view details')

                def update_side_panel(target_info: Dict[str, Any]):
                    """Update the side panel with target details."""
                    target: XTarget | None = target_info.get('target', None)
                    if target is None:
                        return

                    pages: set[PageMapperEntry] = target_info.get(
                        'pages', set())

                    side_panel.clear()
                    with side_panel:
                        ui.label('Object Details').classes(
                            'text-xl font-bold mb-4 text-white')

                        # Type badge
                        create_type_badge(target.target_type.value)

                        # Tag and GUID
                        with create_collapsible_section('label', 'Identification', default_open=True):
                            with ui.column().classes('p-3'):
                                create_info_card(
                                    'Tag', target.tag.tag_str, 'font-mono text-sm')
                                create_info_card(
                                    'GUID', target.get_guid(), 'font-mono text-xs')

                        # Attributes
                        if target.attributes:
                            with create_collapsible_section('settings', f'Attributes ({len(target.attributes)})', default_open=True):
                                with ui.column().classes('gap-2 p-3'):
                                    for attr in target.attributes:
                                        with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-3'):
                                            ui.label(f'{attr}').classes(
                                                'text-sm text-gray-200')

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

                def refresh_tree():
                    """Refresh the tree data from the manager."""
                    tree_data = state.manager.get_tree()
                    # Ensure tree_data is not None
                    if tree_data is None:
                        tree_data = []
                    print(f"Refreshing tree with {len(tree_data)} nodes")
                    
                    # Re-index targets when refreshing
                    searcher.index_targets(state.manager.god.xtargets)
                    
                    tree_container.clear()
                    with tree_container:
                        create_tree_outline(
                            tree_data, update_side_panel, state, searcher)

                # Initial load
                refresh_tree()
