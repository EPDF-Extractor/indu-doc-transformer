from typing import Callable
from nicegui import ui
from gui.aspects_menu import make_config_opener
from gui.global_state import ClientState
from indu_doc.plugin_base import AMLBuilder
from indu_doc.configs import AspectsConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


def export_aml_callback(state: ClientState):
    if not state.manager:
        logger.warning("Manager not initialized, cannot export AML.")
        ui.notify("No data to export", color='negative')
        return
    builder = AMLBuilder(state.manager.god, state.manager.configs)
    print("()" * 100)
    p = state.manager.god.links["cc308c2f-c0f5-5dfa-d344-375f1cd8fb3e"].get_guid()
    print(p)
    print(state.manager.god.links["cc308c2f-c0f5-5dfa-d344-375f1cd8fb3e"])
    print("()" * 100)

    aml = builder.process()
    ui.download.content(aml, 'exported_data.aml')


def create_secondary_action_buttons(state):
    """Create the secondary action buttons section (row of square icon+text buttons)."""
    with ui.row().classes('w-full justify-center gap-6 py-4'):
        actions = [
            ('View Tree', 'account_tree', tree_page_callback),
            ('View Connections', 'cable', connections_page_callback),
            ('View Uploaded Files', 'feed', preview_page_callback),
            ('Export to AML', 'ios_share', lambda: export_aml_callback(state))
        ]
        for label, icon, handler in actions:
            with ui.button(on_click=handler, color='primary').props('flat').classes(
                    'w-32 h-32 flex flex-col items-center justify-center gap-2 border-2 border-gray-600 hover:border-blue-500 hover:bg-gray-700 transition-all').bind_enabled(state.manager, 'has_data'):
                ui.icon(icon).classes('text-4xl text-blue-400')
                ui.separator().classes('w-full border-t visible md:invisible')
                ui.label(label).classes('text-sm font-semibold text-gray-200')


def create_top_section(config_dialog, extract_callback: Callable, progress_callback: Callable, state):
    """Create the top section with PDF list and primary action buttons."""
    from . import pdf_handler
    with ui.row().classes('w-full p-4 gap-8'):
        pdf_list_container = pdf_handler.create_pdf_picker(state)
        create_primary_action_buttons(
            config_dialog, extract_callback, progress_callback)
    return pdf_list_container


def create_bottom_section(state):
    """Create the bottom section with secondary action buttons."""
    with ui.row().classes('w-full p-4 gap-8'):
        create_secondary_action_buttons(state)


def create_main_content(config_dialog, extract_callback: Callable, progress_callback: Callable, state):
    """Create the main content area with top and bottom sections."""
    with ui.column().classes('w-full'):
        create_top_section(config_dialog, extract_callback,
                           progress_callback, state)
        ui.separator()
        create_bottom_section(state)


def create_gui(state: ClientState):
    """Create the main graphical user interface."""
    # Progress monitoring variables
    progress_dialog = None
    progress_label = None
    progress_bar = None
    cancel_button = None
    progress_timer = None

    def show_progress_dialog():
        """Show the progress monitoring dialog."""
        nonlocal progress_dialog, progress_label, progress_bar, cancel_button
        progress_dialog = ui.dialog().props('persistent')
        with progress_dialog:
            with ui.card().classes('bg-gray-800 border-2 border-gray-600 min-w-96'):
                with ui.card_section().classes('bg-gray-800'):
                    ui.label('Processing PDFs...').classes(
                        'text-xl font-bold text-white')
                    progress_label = ui.label(
                        'Initializing...').classes('text-gray-200 mt-2')
                    progress_bar = ui.linear_progress(
                        0, show_value=False).classes('mt-4').props('color=blue-5 size=8px')
                with ui.card_section().classes('bg-gray-800 pt-0'):
                    cancel_button = ui.button('Cancel', color='negative',
                                              on_click=lambda: state.manager.stop_processing()).props('color=red-6').classes('w-full font-semibold')

        progress_dialog.open()

    def hide_progress_dialog():
        """Hide the progress monitoring dialog."""
        nonlocal progress_dialog, progress_timer
        if progress_dialog:
            progress_dialog.close()
            progress_dialog = None
        if progress_timer:
            progress_timer.cancel()
            progress_timer = None

    def update_progress():
        """Update progress information in the dialog."""
        if not state.manager.is_processing():
            # Processing finished, handle completion
            hide_progress_dialog()

            state_info = state.manager.get_processing_state()
            if state_info['state'] == 'error':
                ui.notify(
                    f'Processing failed: {state_info["error_message"]}', color='negative')
            elif state_info['state'] == 'idle':
                # Show success stats - tree refresh is now handled separately on the tree page
                stats = state.manager.get_stats()
                ui.notify(
                    f'Extraction complete! Found {stats["num_xtargets"]} targets. Go to Tree View to see results.', color='positive')
            return

        # Update progress display
        state_info = state.manager.get_processing_state()
        progress = state_info['progress']

        if progress_label and progress_bar:
            # Update progress text
            if progress['current_file']:
                filename = progress['current_file'].split(
                    '\\')[-1]  # Get just filename
                progress_label.text = f"Processing: {filename} ({progress['current_page']}/{progress['total_pages']})"
            else:
                progress_label.text = f"Page {progress['current_page']} of {progress['total_pages']}"

            # Update progress bar
            progress_bar.value = progress['percentage']

    def extract_pdfs(progress_callback):
        """Extract data from uploaded PDFs and update tree."""
        if not state.uploaded_pdfs:
            ui.notify('No PDFs uploaded', color='negative')
            return

        # Check if already processing
        if state.manager.is_processing():
            ui.notify('Processing already in progress', color='warning')
            return

        try:
            # Update manager config in case aspects were modified
            current_aspects_config = AspectsConfig.init_from_list([
                {"Aspect": aspect.Aspect, "Separator": aspect.Separator}
                for aspect in state.aspects
            ])
            state.manager.update_configs(current_aspects_config)

            # Start processing (non-blocking)
            ui.notify('Starting PDF processing...', color='info')
            state.manager.process_pdfs(state.uploaded_pdfs)

            # Start progress monitoring
            progress_callback()

        except Exception as e:
            logger.error(f"Error starting extraction: {e}")
            ui.notify(f'Error starting extraction: {str(e)}', color='negative')

    def start_progress_monitoring():
        """Start the progress monitoring with timer."""
        nonlocal progress_timer
        show_progress_dialog()
        # Use NiceGUI timer to update progress every 500ms
        progress_timer = ui.timer(0.5, update_progress)

    # Create main view
    with ui.card().classes('w-full h-full no-shadow border-2 border-gray-700 bg-gray-900'):
        ui.label('Home View').classes(
            'text-2xl font-bold w-full text-center text-white py-4')
        create_main_content(make_config_opener(state.aspects),
                            extract_pdfs, start_progress_monitoring,  state)
