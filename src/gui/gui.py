import uuid
from nicegui import app, ui, Client

from gui.connections_page import create_connections_page
from gui.global_state import ClientState, clients_to_state
from gui.pdf_preview_page import create_pdf_preview_page
from gui.tree_page import create_tree_page
from gui.ui_components import create_gui

# Register tree page route


@ui.page('/tree', dark=True)
def tree_page():
    state = clients_to_state.get(app.storage.browser['id'])
    if state:
        create_tree_page(state)
    else:
        ui.label('Manager not initialized. Please go back to home page.').classes(
            'text-red-400 text-xl')


# Register connections page route
@ui.page('/connections', dark=True)
def connections_page():
    state = clients_to_state.get(app.storage.browser['id'])
    if state:
        create_connections_page(state)
    else:
        ui.label('Manager not initialized. Please go back to home page.').classes(
            'text-red-400 text-xl')


# Register PDF preview page route
@ui.page('/pdf-preview', dark=True)
def pdf_preview_page(file: str = '', page: int = 1):
    state = clients_to_state.get(app.storage.browser['id'])
    if state:
        create_pdf_preview_page(state, file, int(page))
    else:
        ui.label('Manager not initialized. Please go back to home page.').classes(
            'text-red-400 text-xl')


@ui.page('/', dark=True)
def main_page(client: Client):
    state = ClientState()
    print(app.storage.browser['id'])
    clients_to_state[app.storage.browser['id']] = state
    print(clients_to_state)
    create_gui(state)


if __name__ in {"__main__", "__mp_main__"}:
    """Entry point for running the GUI application."""
    app.add_static_files(url_path='../../static', local_directory='static')
    ui.run(storage_secret=str(uuid.uuid4()),
           title="InduDoc Transformer",  dark=True, favicon='static/logo.jpeg')
