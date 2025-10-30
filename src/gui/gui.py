import uuid
from nicegui import app, ui, Client

from gui.connections_page import create_connections_page
from gui.global_state import ClientState, clients_to_state, get_state, IS_EXE_MODE, USE_NATIVE_WINDOW
from gui.pdf_preview_page import create_pdf_preview_page
from gui.tree_page import create_tree_page
from gui.ui_components import create_gui

# Register tree page route


@ui.page('/tree', dark=True)
def tree_page():
    client_id = None if IS_EXE_MODE else app.storage.browser.get('id')
    state = get_state(client_id)
    if state:
        create_tree_page(state)
    else:
        ui.label('Manager not initialized. Please go back to home page.').classes(
            'text-red-400 text-xl')


# Register connections page route
@ui.page('/connections', dark=True)
def connections_page():
    client_id = None if IS_EXE_MODE else app.storage.browser.get('id')
    state = get_state(client_id)
    if state:
        create_connections_page(state)
    else:
        ui.label('Manager not initialized. Please go back to home page.').classes(
            'text-red-400 text-xl')


# Register PDF preview page route
@ui.page('/pdf-preview', dark=True)
async def pdf_preview_page(file: str = '', page: int = 1):
    await ui.context.client.connected()
    client_id = None if IS_EXE_MODE else app.storage.browser.get('id')
    state = get_state(client_id)
    if state:
        if not IS_EXE_MODE:
            app.storage.tab['current_pdf_file'] = file
        create_pdf_preview_page(state, file, int(page))
    else:
        ui.label('Manager not initialized. Please go back to home page.').classes(
            'text-red-400 text-xl')


@ui.page('/', dark=True)
def main_page(client: Client):
    if IS_EXE_MODE:
        # In EXE mode, use global state (always returns a valid state)
        state = get_state()
    else:
        # In browser mode, use per-client state
        state = ClientState()
        client_id = app.storage.browser['id']
        print(f"Browser client ID: {client_id}")
        clients_to_state[client_id] = state
        print(f"Active clients: {len(clients_to_state)}")
    
    if state:
        create_gui(state)


if __name__ in {"__main__", "__mp_main__"}:
    """Entry point for running the GUI application."""
    app.add_static_files(url_path='../../static', local_directory='static')
    
    # Configure run parameters based on mode
    run_kwargs = {
        'title': "InduDoc Transformer",
        'dark': True,
        'favicon': 'static/logo.jpeg'
    }
    
    if IS_EXE_MODE:
        # EXE mode: Use global state, optionally with native window
        import logging
        
        if USE_NATIVE_WINDOW:
            logging.info("Running in EXE mode with native window")
            run_kwargs['native'] = True
            run_kwargs['reload'] = False
            run_kwargs['window_size'] = (1280, 800)
        else:
            logging.info("Running in EXE mode with browser window")
            run_kwargs['reload'] = False
            run_kwargs['show'] = True  # Open browser automatically
        # No storage_secret needed in EXE mode (using global state)
    else:
        # Browser mode: Require storage_secret for browser-based storage
        run_kwargs['storage_secret'] = str(uuid.uuid4())
    
    ui.run(**run_kwargs)
