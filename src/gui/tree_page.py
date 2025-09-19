from nicegui import ui
from typing import List, Dict, Any
from indu_doc.manager import Manager
from gui.global_state import manager


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


# Custom recursive filter for tree nodes by description
def filter_tree_by_description(tree_data: List[Dict[str, Any]], filter_str: str) -> List[Dict[str, Any]]:
    if not filter_str:
        return tree_data
    filter_str = filter_str.lower().strip()
    filtered = []
    for node in tree_data:
        # Check if description matches (case-insensitive)
        desc = str(node.get('description', '')).split('\n')[0].lower()

        match = filter_str.lower() in desc
        print(
            f"Filtering node {node.get('id')} with description '{desc}': {'MATCH' if match else 'NO MATCH'}")
        # Recursively filter children
        children = node.get('children', [])
        filtered_children = filter_tree_by_description(
            children, filter_str) if children else []
        if match or filtered_children:
            new_node = node.copy()
            new_node['children'] = filtered_children
            filtered.append(new_node)
    return filtered


def create_tree_outline(tree_data: List[Dict[str, Any]]):
    """Create the tree outline section for the dedicated tree page with custom description filter."""
    # Remove the nested card wrapper
    ui.label('Tree Outline').classes(
        'text-center w-full text-xl font-semibold mb-2')
    safe_tree_data = sanitize_tree_data(
        tree_data if tree_data is not None else [])
    ui.label(f'Total nodes: {len(safe_tree_data)}').classes(
        'text-center w-full text-sm text-gray-600 mb-4')

    filter_input = ui.input(
        'Filter by description...').classes('w-full mb-4')

    # Create a container for the tree that will take remaining space
    with ui.element('div').classes('flex-1 overflow-auto border border-gray-300 rounded p-2 w-full'):
        tree_section = ui.element('div').classes('w-full h-full')

        def handle_click(e):
            v = e.value[e.value.find(":")+1:].strip()
            ui.clipboard.write(v)
            ui.notify(f'Copied to clipboard: {v}')

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
                    ).props(add='selected-color=primary no-transition').classes('png-tree-icon w-full max-w-full')
                    tree.add_slot('default-header', '''
                    <span :props="props"><strong>{{ props.node.id }}</strong></span>
                    ''')
                    tree.add_slot('default-body', '''
                        <div v-if="props.node.description" v-html="props.node.description.replace(/\\n/g, '<br>')"></div>
                    ''')
            else:
                with tree_section:
                    ui.label('No data available. Please extract PDFs first or adjust your filter.').classes(
                        'text-center text-gray-500')

        filter_input.on_value_change(lambda e: update_tree())
        # Initial render
        update_tree()


def create_tree_page():
    """Create a dedicated page for displaying the tree structure."""
    ui.dark_mode().enable()
    with ui.card().classes('w-full h-screen no-shadow border-[1px] border-gray-300 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0'):
            with ui.row().classes('w-full items-center'):
                ui.label('Tree View').classes(
                    'text-xl font-semibold flex-grow text-center')
                ui.button('Refresh', on_click=lambda: refresh_tree()
                          ).classes('ml-4')

        ui.separator()

        # Tree content
        with ui.card_section().classes('flex-1 flex flex-col min-h-0 w-full max-w-full overflow-hidden'):
            tree_container = ui.column().classes(
                'w-full max-w-full flex-1 flex flex-col overflow-hidden')

            def refresh_tree():
                """Refresh the tree data from the manager."""
                tree_data = manager.get_tree()
                # Ensure tree_data is not None
                if tree_data is None:
                    tree_data = []
                print(f"Refreshing tree with {len(tree_data)} nodes")
                tree_container.clear()
                with tree_container:
                    create_tree_outline(tree_data)

            # Initial load
            refresh_tree()
