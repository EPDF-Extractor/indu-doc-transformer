from typing import Any, Callable
from nicegui import ui, run
from gui.aspects_menu import make_config_opener
from gui.global_state import ClientState
from indu_doc.plugins.aml_builder.aml_builder import AMLBuilder
from indu_doc.configs import AspectsConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_primary_action_buttons(config_dialog, extract_callback: Callable):
    """Create the primary action buttons section."""

    with ui.column().classes('gap-3 min-w-48'):
        ui.button('Configuration', on_click=config_dialog.open).classes(
            'w-full text-base font-semibold').props('outline color=blue-5')
        ui.button('Extract', color='positive',
                  on_click=extract_callback).classes('w-full text-base font-semibold').props('color=green-6')


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

    builder.process()
    aml = builder.output_str()
    ui.download.content(aml, 'exported_data.aml')


def create_secondary_action_buttons(state):
    """Create the secondary action buttons section (row of square icon+text buttons)."""
    with ui.row().classes('w-full justify-center gap-6 py-4'):
        actions = [
            ('View Tree', 'account_tree', tree_page_callback),
            ('View Connections', 'cable', connections_page_callback),
            ('View Uploaded Files', 'feed', preview_page_callback),
            ('Export to AML', 'ios_share', lambda: export_aml_callback(state)),
        ]
        for label, icon, handler in actions:
            with ui.button(on_click=handler, color='primary').props('flat').classes(
                    'w-32 h-32 flex flex-col items-center justify-center gap-2 border-2 border-gray-600 hover:border-blue-500 hover:bg-gray-700 transition-all').bind_enabled(state.manager, 'has_data'):
                ui.icon(icon).classes('text-4xl text-blue-400')
                ui.separator().classes('w-full border-t visible md:invisible')
                ui.label(label).classes('text-sm font-semibold text-gray-200')


def create_top_section(config_dialog, extract_callback: Callable, state):
    """Create the top section with PDF list and primary action buttons."""
    from . import pdf_handler
    with ui.row().classes('w-full p-4 gap-8'):
        pdf_list_container = pdf_handler.create_pdf_picker(state)
        create_primary_action_buttons(config_dialog, extract_callback)
    return pdf_list_container


def create_bottom_section(state):
    """Create the bottom section with secondary action buttons."""
    with ui.row().classes('w-full p-4 gap-8'):
        create_secondary_action_buttons(state)


def create_main_content(config_dialog, extract_callback: Callable, state):
    """Create the main content area with top and bottom sections."""
    with ui.column().classes('w-full'):
        create_top_section(config_dialog, extract_callback, state)
        ui.separator()
        create_bottom_section(state)


def create_gui(state: ClientState):
    """Create the main graphical user interface."""
    # Progress monitoring variables
    progress_dialog = None
    progress_label = None
    progress_bar = None
    cancel_button = None
    was_processing = False  # Track previous processing state

    def show_progress_dialog():
        """Show the progress monitoring dialog."""
        nonlocal progress_dialog, progress_label, progress_bar, cancel_button
        if progress_dialog:  # Already showing
            return
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
        nonlocal progress_dialog
        if progress_dialog:
            progress_dialog.close()
            progress_dialog = None

    def check_and_update_progress():
        """Automatically check if processing is active and update progress."""
        nonlocal was_processing
        
        is_processing = state.manager.is_processing()
        
        # Show dialog when processing starts
        if is_processing and not was_processing:
            show_progress_dialog()
        
        # Hide dialog when processing stops
        if not is_processing and was_processing:
            hide_progress_dialog()

            states: list[dict[str, Any]] = state.manager.get_processing_state()
            
            # Check if processing completed successfully or with errors
            if states:
                # Check for errors
                has_errors = any(s['state'] == 'error' for s in states)
                all_done = all(s['progress']['is_done'] for s in states)
                
                if has_errors:
                    error_messages = [s.get('error_message', 'Unknown error') 
                                    for s in states if s['state'] == 'error']
                    ui.notify(f'Processing failed: {"; ".join(error_messages)}', color='negative')
                elif all_done:
                    ui.notify('Processing completed successfully', color='positive')
        
        # Update progress if currently processing
        if is_processing:
            states: list[dict[str, Any]] = state.manager.get_processing_state()
            
            if states:
                # Aggregate progress from all plugins
                total_current = 0
                total_pages = 0
                current_files = []
                
                for state_info in states:
                    if state_info['state'] == 'processing':
                        progress = state_info['progress']
                        total_current += progress['current_page']
                        total_pages += progress['total_pages']
                        if progress['current_file']:
                            current_files.append(progress['current_file'])
                
                if progress_label and progress_bar:
                    # Update progress text
                    if current_files:
                        # Show first file being processed
                        filename = current_files[0].split('\\')[-1]  # Get just filename
                        if len(current_files) > 1:
                            progress_label.text = f"Processing: {filename} and {len(current_files)-1} more... ({total_current}/{total_pages})"
                        else:
                            progress_label.text = f"Processing: {filename} ({total_current}/{total_pages})"
                    else:
                        progress_label.text = f"Page {total_current} of {total_pages}"

                    # Update progress bar
                    if total_pages > 0:
                        percentage = (total_current / total_pages) * 100
                        progress_bar.value = percentage / 100
                    else:
                        progress_bar.value = 0
        
        # Update tracking variable
        was_processing = is_processing

    async def extract_pdfs():
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
            # Run it as blocking in another thread to avoid blocking the UI
            await run.io_bound(state.manager.process_files, tuple(state.uploaded_pdfs), True)

        except Exception as e:
            logger.error(f"Error starting extraction: {e}")
            ui.notify(f'Error starting extraction: {str(e)}', color='negative')

    # Start automatic progress monitoring timer that runs continuously
    # Check every 500ms if processing state has changed
    ui.timer(0.5, check_and_update_progress)

    # Create main view
    with ui.card().classes('w-full h-full no-shadow border-2 border-gray-700 bg-gray-900'):
        ui.label('Home View').classes(
            'text-2xl font-bold w-full text-center text-white py-4')
        create_main_content(make_config_opener(state.aspects),
                            extract_pdfs, state)
