from nicegui import ui
from typing import List, Dict, Any
from gui.global_state import ClientState
from indu_doc.god import PageMapperEntry
from indu_doc.xtarget import XTarget
from gui.detail_panel_components import (
    create_type_badge, create_info_card, create_attributes_section,
    create_occurrences_section, create_empty_state
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


# Custom recursive filter for tree nodes by tag_str or GUID
def filter_tree_by_description(tree_data: List[Dict[str, Any]], filter_str: str) -> List[Dict[str, Any]]:
    if not filter_str:
        return tree_data
    filter_str = filter_str.lower().strip()
    filtered = []
    for node in tree_data:
        # Extract tag_str and GUID from description HTML
        desc = node.get('description', '')
        node_id = str(node.get('id', '')).lower()

        # Check if filter matches tag_str (node id) or GUID (extract from description)
        match = filter_str in node_id

        # Try to extract GUID from description if it exists
        if not match and desc:
            import re
            guid_match = re.search(r'<code>([^<]+)</code>', desc)
            if guid_match:
                guid = guid_match.group(1).lower()
                match = filter_str in guid

        # Recursively filter children
        children = node.get('children', [])
        filtered_children = filter_tree_by_description(
            children, filter_str) if children else []
        if match or filtered_children:
            new_node = node.copy()
            new_node['children'] = filtered_children
            filtered.append(new_node)
    return filtered


def create_tree_outline(tree_data: List[Dict[str, Any]], details_callback, state: ClientState):
    """Create the tree outline section for the dedicated tree page with custom description filter."""
    ui.label('Tree Outline').classes(
        'text-center w-full text-xl font-semibold mb-2 text-white')
    safe_tree_data = sanitize_tree_data(
        tree_data if tree_data is not None else [])
    ui.label(f'Total nodes: {len(safe_tree_data)}').classes(
        'text-center w-full text-sm text-gray-300 mb-4')

    filter_input = ui.input(
        'Filter by tag or GUID...').classes('w-full mb-4').props('dark outlined')

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
            filter_str = filter_input.value or ''
            filtered = filter_tree_by_description(safe_tree_data, filter_str)
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
    with ui.card().classes('w-full h-screen no-shadow border-2 border-gray-700 bg-gray-900 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0 bg-gray-800'):
            with ui.row().classes('w-full items-center'):
                ui.label('Tree View').classes(
                    'text-2xl font-bold flex-grow text-center text-white')
                ui.button('Refresh', on_click=lambda: refresh_tree()
                          ).classes('ml-4').props('outline color=blue-5')

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
                        create_info_card(
                            'Tag', target.tag.tag_str, 'font-mono text-sm')
                        create_info_card(
                            'GUID', target.get_guid(), 'font-mono text-xs')

                        # Attributes
                        create_attributes_section(target.attributes)

                        # Occurrences
                        create_occurrences_section(pages)

                def refresh_tree():
                    """Refresh the tree data from the manager."""
                    tree_data = state.manager.get_tree()
                    # Ensure tree_data is not None
                    if tree_data is None:
                        tree_data = []
                    print(f"Refreshing tree with {len(tree_data)} nodes")
                    tree_container.clear()
                    with tree_container:
                        create_tree_outline(
                            tree_data, update_side_panel, state)

                # Initial load
                refresh_tree()
