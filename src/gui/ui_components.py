from typing import Any, Callable
from nicegui import ui, run
from gui.aspects_menu import make_config_opener
from gui.global_state import ClientState
from indu_doc.exporters.aml_builder.aml_exporter import AMLExporter
from indu_doc.exporters.db_builder.db_exporter import SQLITEDBExporter
from indu_doc.configs import AspectsConfig
from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
import logging
import tempfile
import os
import json


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_primary_action_buttons(config_dialog, extract_callback: Callable, state: ClientState, import_callback: Callable, page_settings_callback: Callable):
    """Create the primary action buttons section."""

    with ui.column().classes('gap-3 min-w-48'):
        ui.button('Configuration', on_click=config_dialog.open).classes(
            'w-full text-base font-semibold').props('outline color=blue-5')
        
        # Page Settings button - always enabled
        ui.button('Page Settings', on_click=page_settings_callback).classes(
            'w-full text-base font-semibold').props('outline color=purple-5').style('color: #A78BFA')
        
        # Import Data button - always enabled
        ui.button('Import Data', on_click=import_callback).classes(
            'w-full text-base font-semibold').props('outline color=blue-5').style('color: #60A5FA')
        
        # Extract button - disabled if no pending files
        extract_button = ui.button('Extract', color='positive',
                  on_click=extract_callback).classes('w-full text-base font-semibold').props('color=green-6')
        
        # Function to check if there are pending files
        def has_pending_files():
            pending_count = len([f for f in state.uploaded_pdfs if f not in state.processed_files])
            return pending_count > 0
        
        # Update button state and tooltip
        def update_extract_button():
            has_pending = has_pending_files()
            extract_button.enabled = has_pending
            if has_pending:
                pending_count = len([f for f in state.uploaded_pdfs if f not in state.processed_files])
                extract_button.tooltip(f'Extract data from {pending_count} pending file(s)')
            else:
                extract_button.tooltip('No pending files to extract. Import PDFs first.')
        
        # Initial update
        update_extract_button()
        
        # Update button state periodically
        ui.timer(1.0, update_extract_button)


def tree_page_callback():
    ui.navigate.to("/tree", new_tab=True)


def connections_page_callback():
    ui.navigate.to("/connections", new_tab=True)


def preview_page_callback():
    ui.navigate.to("/pdf-preview?file=", new_tab=True)


async def export_data_callback(state: ClientState, export_format: str):
    """Export data in the selected format (AML or SQLite DB)."""
    if not state.manager:
        logger.warning("Manager not initialized, cannot export data.")
        ui.notify("No data to export", color='negative')
        return
    
    try:
        if export_format == 'aml':
            # Export as AML (fast, no need for io_bound)
            ui.notify('Exporting AML...', color='info')
            data_stream = AMLExporter.export_data(state.manager.god)
            ui.download(data_stream.read(), 'exported_data.aml')
            ui.notify('AML file exported successfully', color='positive')
        elif export_format == 'sqlite':
            # Export as SQLite database (IO-bound operation)
            ui.notify('Exporting database... Please wait', color='info')
            data_stream = await run.io_bound(SQLITEDBExporter.export_data, state.manager.god)
            ui.download(data_stream.read(), 'exported_data.db')
            ui.notify('SQLite database exported successfully', color='positive')
        else:
            ui.notify(f'Unknown export format: {export_format}', color='negative')
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        ui.notify(f'Export failed: {str(e)}', color='negative')


def show_export_dialog(state: ClientState):
    """Show a dialog to choose export format and download the file."""
    export_format = {'value': 'aml'}  # Default format
    
    async def handle_export():
        await export_data_callback(state, export_format['value'])
        dialog.close()
    
    dialog = ui.dialog()
    with dialog, ui.card().classes('bg-gray-800 border-2 border-gray-600 min-w-96'):
        with ui.card_section().classes('bg-gray-800'):
            ui.label('Export Data').classes('text-xl font-bold text-white')
            ui.label('Choose export format:').classes('text-gray-200 mt-2')
            
            with ui.column().classes('w-full gap-2 mt-4'):
                ui.select(
                    options={
                        'aml': 'AML Format (.aml)',
                        'sqlite': 'SQLite Database (.db)'
                    },
                    value='aml',
                    label='Export Format'
                ).classes('w-full').bind_value(export_format, 'value')
        
        with ui.card_section().classes('bg-gray-800 pt-0'):
            with ui.row().classes('w-full gap-2 justify-end'):
                ui.button('Cancel', on_click=dialog.close).props('flat color=gray')
                ui.button(
                    'Export',
                    color='primary',
                    on_click=handle_export
                ).props('color=blue-6')
    
    dialog.open()


async def import_from_db_callback(state: ClientState, db_file_content: bytes, filename: str):
    """Import data from a SQLite database file."""
    if not state.manager:
        logger.warning("Manager not initialized, cannot import data.")
        ui.notify("Manager not initialized", color='negative')
        return
    
    try:
        ui.notify(f'Importing database {filename}... Please wait', color='info')
        
        # Create a temporary directory for extracted documents
        extract_dir = tempfile.mkdtemp(prefix='indu_doc_import_')
        logger.info(f"Extracting documents to: {extract_dir}")
        
        # Import from the database (IO-bound operation)
        from io import BytesIO
        db_stream = BytesIO(db_file_content)
        imported_god = await run.io_bound(SQLITEDBExporter.import_from_bytes, db_stream, extract_dir)
        
        # Merge the imported God into the current manager's God
        state.manager.god += imported_god
        
        # Add extracted PDF files to uploaded_pdfs list
        imported_files = list(imported_god.pages_mapper.file_paths)
        for file_path in imported_files:
            if os.path.exists(file_path) and file_path not in state.uploaded_pdfs:
                state.uploaded_pdfs.append(file_path)
                state.processed_files.add(file_path)  # Mark as processed
                logger.info(f"Added imported file to state: {file_path}")
        
        file_count = len(imported_files)
        ui.notify(f'Successfully imported data from {filename} ({file_count} file(s))', color='positive')
        
    except Exception as e:
        logger.error(f"Error importing database: {e}", exc_info=True)
        ui.notify(f'Import failed: {str(e)}', color='negative')


def show_import_dialog(state: ClientState, upload_component=None):
    """Show a dialog to upload PDFs and/or import a database file."""
    uploaded_db = {'content': None, 'name': None}
    uploaded_pdfs = []
    
    dialog = ui.dialog()
    with dialog, ui.card().classes('bg-gray-800 border-2 border-gray-600 min-w-[600px]'):
        with ui.card_section().classes('bg-gray-800'):
            ui.label('Import Data').classes('text-xl font-bold text-white')
            
            # Database import section
            ui.label('Import from Database').classes('text-lg font-semibold text-white mt-4')
            ui.label('Upload a SQLite database file (.db):').classes('text-gray-200 mt-2')
            
            with ui.column().classes('w-full gap-2 mt-2'):
                ui.upload(
                    on_upload=lambda e: handle_db_upload(e, uploaded_db),
                    auto_upload=True,
                    multiple=False,
                ).props('dark accept=.db color=blue-5 label="Upload Database File"').classes('w-full')
            
            ui.separator().classes('my-4')
            
            # PDF upload section
            ui.label('Upload PDF Files').classes('text-lg font-semibold text-white')
            ui.label('Upload PDF files to extract data from:').classes('text-gray-200 mt-2')
            
            with ui.column().classes('w-full gap-2 mt-2'):
                ui.upload(
                    on_upload=lambda e: handle_pdf_upload_in_dialog(e, uploaded_pdfs),
                    auto_upload=True,
                    multiple=True,
                ).props('dark accept=.pdf color=green-5 label="Upload PDF Files"').classes('w-full')
        
        with ui.card_section().classes('bg-gray-800 pt-0'):
            with ui.row().classes('w-full gap-2 justify-end'):
                ui.button('Cancel', on_click=dialog.close).props('flat color=gray')
                ui.button(
                    'Import',
                    color='primary',
                    on_click=lambda: (
                        import_and_close_combined(state, uploaded_db, uploaded_pdfs, dialog)
                    )
                ).props('color=blue-6')
    
    dialog.open()


def handle_pdf_upload_in_dialog(e, uploaded_pdfs: list):
    """Handle PDF file upload in the import dialog."""
    if not e.content:
        ui.notify('No file selected', color='warning')
        return
    
    filename = e.name
    if not filename.lower().endswith('.pdf'):
        ui.notify('Please upload a PDF file', color='negative')
        return
    
    # Save to temp directory
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    
    try:
        with open(file_path, 'wb') as f:
            f.write(e.content.read())
        
        uploaded_pdfs.append(file_path)
        ui.notify(f'Added {filename}', color='positive')
    except Exception as ex:
        ui.notify(f'Error uploading {filename}: {str(ex)}', color='negative')


def handle_db_upload(e, uploaded_db: dict):
    """Handle database file upload for import."""
    if not e.content:
        ui.notify('No file selected', color='warning')
        return
    
    filename = e.name
    if not filename.lower().endswith('.db'):
        ui.notify('Please upload a .db file', color='negative')
        return
    
    uploaded_db['content'] = e.content.read()
    uploaded_db['name'] = filename
    ui.notify(f'Uploaded {filename}', color='positive')


async def import_and_close(state: ClientState, uploaded_db: dict, dialog, upload_component=None):
    """Import the database and close the dialog."""
    if uploaded_db['content']:
        await import_from_db_callback(state, uploaded_db['content'], uploaded_db['name'])
        dialog.close()


async def import_and_close_combined(state: ClientState, uploaded_db: dict, uploaded_pdfs: list, dialog):
    """Import database and/or PDFs, then close the dialog."""
    imported_anything = False
    
    # Import database if provided
    if uploaded_db['content']:
        await import_from_db_callback(state, uploaded_db['content'], uploaded_db['name'])
        imported_anything = True
    
    # Add uploaded PDFs to state
    if uploaded_pdfs:
        for file_path in uploaded_pdfs:
            if os.path.exists(file_path) and file_path not in state.uploaded_pdfs:
                state.uploaded_pdfs.append(file_path)
                logger.info(f"Added PDF to state: {file_path}")
        
        ui.notify(f'Added {len(uploaded_pdfs)} PDF file(s)', color='positive')
        imported_anything = True
    
    if not imported_anything:
        ui.notify('No files were uploaded', color='warning')
    else:
        dialog.close()


def update_page_settings_callback(state: ClientState, json_content: bytes, filename: str):
    """Update page settings from an uploaded JSON file."""
    if not state.manager:
        logger.warning("Manager not initialized, cannot update page settings.")
        ui.notify("Manager not initialized", color='negative')
        return
    
    try:
        # Validate JSON content
        json_str = json_content.decode('utf-8')
        _ = json.loads(json_str)  # Validate it's proper JSON
        
        # Create a temporary file to store the settings
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
        temp_file.write(json_str)
        temp_file.close()
        
        # Create new PageSettings from the uploaded file
        new_page_settings = PageSettings(temp_file.name)
        
        # Update the plugin's page settings
        # Get the plugin from manager
        plugins = state.manager.plugins
        updated_count = 0
        for plugin in plugins:
            # Check if it's an EplanPDFPlugin or has page_settings attribute
            if hasattr(plugin, 'page_settings'):
                setattr(plugin, 'page_settings', new_page_settings)
                logger.info(f"Updated page settings for plugin: {type(plugin).__name__}")
                updated_count += 1
        
        if updated_count == 0:
            ui.notify('No plugins found that support page settings', color='warning')
        else:
            ui.notify(f'Successfully updated page settings from {filename}', color='positive')
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in page settings file: {e}")
        ui.notify(f'Invalid JSON file: {str(e)}', color='negative')
    except Exception as e:
        logger.error(f"Error updating page settings: {e}", exc_info=True)
        ui.notify(f'Failed to update page settings: {str(e)}', color='negative')


def show_page_settings_dialog(state: ClientState):
    """Show a dialog to upload a new page settings JSON file."""
    uploaded_file: dict[str, bytes | str | None] = {'content': None, 'name': None}
    
    def handle_page_settings_upload(e):
        """Handle page settings file upload."""
        if not e.content:
            ui.notify('No file selected', color='warning')
            return
        
        filename = e.name
        if not filename.lower().endswith('.json'):
            ui.notify('Please upload a JSON file', color='negative')
            return
        
        uploaded_file['content'] = e.content.read()
        uploaded_file['name'] = filename
        ui.notify(f'Uploaded {filename}', color='positive')
    
    def handle_update():
        """Handle the update action."""
        if uploaded_file['content'] and uploaded_file['name']:
            update_page_settings_callback(
                state, 
                uploaded_file['content'],  # type: ignore
                uploaded_file['name']  # type: ignore
            )
            dialog.close()
        else:
            ui.notify('No file uploaded', color='warning')
    
    dialog = ui.dialog()
    with dialog, ui.card().classes('bg-gray-800 border-2 border-gray-600 min-w-[500px]'):
        with ui.card_section().classes('bg-gray-800'):
            ui.label('Update Page Settings').classes('text-xl font-bold text-white')
            ui.label('Upload a new page settings JSON file to update extraction configuration:').classes('text-gray-200 mt-2')
            
            with ui.column().classes('w-full gap-2 mt-4'):
                ui.upload(
                    on_upload=handle_page_settings_upload,
                    auto_upload=True,
                    multiple=False,
                ).props('dark accept=.json color=blue-5 label="Upload Page Settings (JSON)"').classes('w-full')
                
                # Info box
                with ui.card().classes('bg-gray-700 mt-4'):
                    with ui.card_section().classes('bg-gray-700 py-2'):
                        ui.label('ℹ️ Information').classes('text-sm font-semibold text-blue-300')
                        ui.label('The page settings file defines how to extract data from different page types. Updating this will affect future extractions.').classes('text-xs text-gray-300 mt-1')
        
        with ui.card_section().classes('bg-gray-800 pt-0'):
            with ui.row().classes('w-full gap-2 justify-end'):
                ui.button('Cancel', on_click=dialog.close).props('flat color=gray')
                ui.button(
                    'Update Settings',
                    color='primary',
                    on_click=handle_update
                ).props('color=blue-6')
    
    dialog.open()


def create_imported_files_list(state: ClientState):
    """Create a simple list display of imported/uploaded files."""
    with ui.card().classes('flex-grow min-w-0 bg-gray-800 border-2 border-gray-600 shadow-lg').style('height: 300px; display: flex; flex-direction: column;'):
        with ui.card_section().classes('bg-gray-750 border-b border-gray-600 py-3'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Imported Files').classes('text-lg font-bold text-white')
                with ui.row().classes('gap-2'):
                    processed_count = len([f for f in state.uploaded_pdfs if f in state.processed_files])
                    pending_count = len(state.uploaded_pdfs) - processed_count
                    if processed_count > 0:
                        ui.badge(f'{processed_count} Processed', color='green').classes('text-xs')
                    if pending_count > 0:
                        ui.badge(f'{pending_count} Pending', color='orange').classes('text-xs')
        
        with ui.card_section().classes('flex-grow overflow-hidden p-3').style('flex: 1; overflow: hidden;'):
            file_list_container = ui.column().classes('w-full gap-2 h-full overflow-y-auto')
            
            def update_file_list():
                """Update the file list display."""
                file_list_container.clear()
                with file_list_container:
                    if not state.uploaded_pdfs:
                        ui.label('No files imported yet.').classes('text-gray-400 text-sm italic text-center py-8')
                    else:
                        for file_path in state.uploaded_pdfs:
                            if os.path.exists(file_path):
                                filename = os.path.basename(file_path)
                                is_processed = file_path in state.processed_files
                                
                                # Different styling for processed vs unprocessed files
                                if is_processed:
                                    bg_class = 'bg-green-900 hover:bg-green-800'
                                    icon_name = 'check_circle'
                                    icon_color = 'text-green-400'
                                    badge_text = 'Processed'
                                    badge_color = 'green'
                                else:
                                    bg_class = 'bg-gray-700 hover:bg-gray-600'
                                    icon_name = 'pending'
                                    icon_color = 'text-yellow-400'
                                    badge_text = 'Pending'
                                    badge_color = 'orange'
                                
                                with ui.row().classes(f'w-full items-center gap-2 p-3 {bg_class} rounded-lg transition-colors'):
                                    ui.icon(icon_name).classes(f'{icon_color} text-2xl')
                                    ui.label(filename).classes('text-gray-200 text-sm flex-grow truncate')
                                    ui.badge(badge_text, color=badge_color).classes('text-xs')
            
            update_file_list()
            
            # Update list periodically to show new imports
            ui.timer(1.0, update_file_list)


def remove_imported_file(state: ClientState, file_path: str):
    """Remove an imported file from the state."""
    if file_path in state.uploaded_pdfs:
        state.uploaded_pdfs.remove(file_path)
        filename = os.path.basename(file_path)
        ui.notify(f'Removed {filename}', color='info')
        
        # Try to delete the file from disk
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {file_path}: {e}")


def create_secondary_action_buttons(state, upload_component=None):
    """Create the secondary action buttons section (row of square icon+text buttons)."""
    with ui.row().classes('w-full justify-center gap-6 py-4'):
        # Actions that require data
        data_dependent_actions = [
            ('View Tree', 'account_tree', tree_page_callback),
            ('View Connections', 'cable', connections_page_callback),
            ('View Uploaded Files', 'feed', preview_page_callback),
            ('Export Data', 'ios_share', lambda: show_export_dialog(state)),
        ]
        
        # Create data-dependent buttons
        for label, icon, handler in data_dependent_actions:
            with ui.button(on_click=handler, color='primary').props('flat').classes(
                    'w-32 h-32 flex flex-col items-center justify-center gap-2 border-2 border-gray-600 hover:border-blue-500 hover:bg-gray-700 transition-all').bind_enabled(state.manager, 'has_data'):
                ui.icon(icon).classes('text-4xl text-blue-400')
                ui.separator().classes('w-full border-t visible md:invisible')
                ui.label(label).classes('text-sm font-semibold text-gray-200')
        
        # Create always-enabled buttons
        for label, icon, handler in always_enabled_actions:
            with ui.button(on_click=handler, color='primary').props('flat').classes(
                    'w-32 h-32 flex flex-col items-center justify-center gap-2 border-2 border-gray-600 hover:border-blue-500 hover:bg-gray-700 transition-all'):
                ui.icon(icon).classes('text-4xl text-blue-400')
                ui.separator().classes('w-full border-t visible md:invisible')
                ui.label(label).classes('text-sm font-semibold text-gray-200')


def create_top_section(config_dialog, extract_callback: Callable, state):
    """Create the top section with file list and primary action buttons."""
    with ui.row().classes('w-full p-4 gap-8'):
        create_imported_files_list(state)
        # Pass import dialog callback to primary action buttons
        create_primary_action_buttons(
            config_dialog, 
            extract_callback, 
            state,
            lambda: show_import_dialog(state, None),
            lambda: show_page_settings_dialog(state)
        )


def create_bottom_section(state):
    """Create the bottom section with secondary action buttons."""
    with ui.row().classes('w-full p-4 gap-8'):
        create_secondary_action_buttons(state, None)


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
    currently_processing_files = []  # Track files being processed in current session

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
        nonlocal was_processing, currently_processing_files
        
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
                    # Mark only the files that were just processed
                    for file_path in currently_processing_files:
                        state.processed_files.add(file_path)
                    ui.notify('Processing completed successfully', color='positive')
                    # Clear the list for next processing session
                    currently_processing_files.clear()
        
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
        nonlocal currently_processing_files
        
        if not state.uploaded_pdfs:
            ui.notify('No PDFs uploaded', color='negative')
            return

        # Filter out already processed files
        pending_files = [f for f in state.uploaded_pdfs if f not in state.processed_files]
        
        if not pending_files:
            ui.notify('No pending files to extract. All files are already processed.', color='info')
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

            # Store which files we're about to process
            currently_processing_files.clear()
            currently_processing_files.extend(pending_files)
            
            # Start processing only pending files (non-blocking)
            ui.notify(f'Starting PDF processing for {len(pending_files)} file(s)...', color='info')
            # Run it as blocking in another thread to avoid blocking the UI
            await run.io_bound(state.manager.process_files, tuple(pending_files), True)

        except Exception as e:
            logger.error(f"Error starting extraction: {e}")
            ui.notify(f'Error starting extraction: {str(e)}', color='negative')
            currently_processing_files.clear()

    # Start automatic progress monitoring timer that runs continuously
    # Check every 500ms if processing state has changed
    ui.timer(0.5, check_and_update_progress)

    # Create main view
    with ui.card().classes('w-full h-full no-shadow border-2 border-gray-700 bg-gray-900'):
        ui.label('Home View').classes(
            'text-2xl font-bold w-full text-center text-white py-4')
        create_main_content(make_config_opener(state.aspects),
                            extract_pdfs, state)
