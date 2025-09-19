from nicegui import ui, run
from .ui_components import create_main_content
from gui.global_state import manager, aspects, config_dialog_handler, uploaded_pdfs
from indu_doc.configs import AspectsConfig
from gui.tree_page import create_tree_page

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register tree page route


@ui.page('/tree')
def tree_page():
    create_tree_page()


def create_gui():
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
            with ui.card().classes():
                with ui.card_section():
                    ui.label('Processing PDFs...').classes(
                        'text-lg font-semibold')
                    progress_label = ui.label('Initializing...')
                    progress_bar = ui.linear_progress(
                        0, show_value=False).classes('mt-2')
                with ui.card_section():
                    cancel_button = ui.button('Cancel', color='negative',
                                              on_click=lambda: manager.stop_processing())

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
        if not manager.is_processing():
            # Processing finished, handle completion
            hide_progress_dialog()

            state_info = manager.get_processing_state()
            if state_info['state'] == 'error':
                ui.notify(
                    f'Processing failed: {state_info["error_message"]}', color='negative')
            elif state_info['state'] == 'idle':
                # Show success stats - tree refresh is now handled separately on the tree page
                stats = manager.get_stats()
                ui.notify(
                    f'Extraction complete! Found {stats["num_xtargets"]} targets. Go to Tree View to see results.', color='positive')
            return

        # Update progress display
        state_info = manager.get_processing_state()
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
        if not uploaded_pdfs:
            ui.notify('No PDFs uploaded', color='negative')
            return

        # Check if already processing
        if manager.is_processing():
            ui.notify('Processing already in progress', color='warning')
            return

        try:
            # Update manager config in case aspects were modified
            current_aspects_config = AspectsConfig.init_from_list([
                {"Aspect": aspect.Aspect, "Separator": aspect.Separator}
                for aspect in aspects
            ])
            manager.update_configs(current_aspects_config)

            # Start processing (non-blocking)
            ui.notify('Starting PDF processing...', color='info')
            manager.process_pdfs(uploaded_pdfs)

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
    with ui.card().classes('w-full h-full no-shadow border-[1px] border-gray-300'):
        ui.label('Home View').classes(
            'text-xl font-semibold w-full text-center')
        create_main_content(config_dialog_handler,
                            extract_pdfs, start_progress_monitoring)


if __name__ in {"__main__", "__mp_main__"}:
    """Entry point for running the GUI application."""
    create_gui()
    dark = ui.dark_mode()
    dark.enable()
    ui.run()
