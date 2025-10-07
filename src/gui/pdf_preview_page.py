from nicegui import ui, app
from typing import Dict, Any
from gui.global_state import ClientState
from gui.detail_panel_components import create_section_header, create_empty_state, create_info_card, create_collapsible_section
import os
import hashlib
from indu_doc.common_page_utils import PageError, ErrorType


def create_pdf_preview_page(state: ClientState, file_path: str = '', page_number: int = 1):
    """Create a PDF preview page with navigation and object details."""
    # If no file specified, show file selection UI
    if file_path is None or file_path.strip() == '':
        with ui.card().classes('w-full h-screen flex items-center justify-center bg-gray-900 border-2 border-gray-700'):
            with ui.column().classes('items-center gap-4'):
                ui.label('PDF Preview').classes(
                    'text-3xl font-bold mb-4 text-white')

                if not state.uploaded_pdfs:
                    ui.label('No PDFs uploaded yet').classes(
                        'text-gray-400 text-lg')
                else:
                    ui.label('Select a PDF to preview:').classes(
                        'text-lg mb-2 text-gray-200')
                    ui.select(
                        options={p: p.split('\\')[-1]
                                 for p in state.uploaded_pdfs},
                        on_change=lambda e: ui.navigate.to(
                            f'/pdf-preview?file={e.value}&page=1')
                    ).classes('w-96').props('dark outlined')
        return

    # Validate file exists in uploaded PDFs
    if file_path not in state.uploaded_pdfs:
        with ui.card().classes('w-full h-screen flex items-center justify-center bg-gray-900 border-2 border-gray-700'):
            ui.label('File not found or not uploaded').classes(
                'text-red-400 text-xl font-semibold')
        return

    # Add PDF as static file to serve it
    try:
        pdf_filename = os.path.basename(file_path)
        # Create unique URL to avoid caching issues
        file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
        pdf_static_path = app.add_static_file(
            local_file=file_path,
            url_path=f'/static/pdf/{file_hash}.pdf'
        )
    except Exception as e:
        with ui.card().classes('w-full h-screen flex items-center justify-center'):
            ui.label(f'Error loading PDF: {str(e)}').classes(
                'text-red-500 text-xl')
        return

    # Add page fragment for navigation
    pdf_url_with_page = f'{pdf_static_path}#page={page_number}'

    with ui.card().classes('w-full h-screen no-shadow border-2 border-gray-700 bg-gray-900 flex flex-col max-w-full'):
        # Header
        with ui.card_section().classes('flex-shrink-0 bg-gray-800'):
            with ui.row().classes('w-full items-center gap-4'):
                ui.label('PDF Preview').classes(
                    'text-2xl font-bold flex-grow text-center text-white')

                ui.select(
                    options={p: p.split('\\')[-1]
                             for p in state.uploaded_pdfs},
                    value=file_path,
                    on_change=lambda e: ui.navigate.to(
                        f'/pdf-preview?file={e.value}&page={page_number}')
                ).classes('w-64').props('dark outlined')

        ui.separator().classes('bg-gray-700')

        # Main content
        with ui.card_section().classes('flex-1 min-h-0 w-full max-w-full overflow-hidden bg-gray-900'):
            with ui.row().classes('w-full h-full gap-4'):
                # PDF viewer (left side)
                with ui.column().classes('flex-1 min-w-0 h-full'):
                    ui.html(
                        f'<embed src="{pdf_url_with_page}" type="application/pdf" width="100%" height="100%" style="border: solid 2px #4b5563; border-radius: 8px;">').classes('w-full h-full')

                # Object panel (right side)
                object_panel = ui.column().classes(
                    'w-96 flex-shrink-0 h-full border-2 border-gray-600 rounded-lg p-4 overflow-y-auto bg-gray-800')

                def update_object_panel():
                    """Update the object panel with objects on the current page."""
                    object_panel.clear()

                    # Get current page
                    file_name = file_path.split('\\')[-1]
                    objects = state.manager.get_objects_on_page(
                        page_number, file_path)

                    with object_panel:
                        ui.label('Objects on this page').classes(
                            'text-xl font-bold mb-4 text-white')

                        # File and page info in collapsible section
                        with create_collapsible_section('info', 'Page Information', default_open=True):
                            with ui.column().classes('p-3 gap-2'):
                                ui.label(f'File: {file_name}').classes(
                                    'text-sm text-gray-200')

                                # Page input with go to button
                                with ui.row().classes('w-full items-center gap-2'):
                                    ui.label('Page:').classes(
                                        'text-sm text-gray-300')
                                    page_input = ui.input(
                                        value=str(page_number),
                                        placeholder='Page number'
                                    ).classes('flex-grow').props('dark outlined dense type=number min=1')
                                    ui.button(
                                        'Go to',
                                        on_click=lambda: ui.navigate.to(
                                            f'/pdf-preview?file={file_path}&page={max(1, int(page_input.value)) if page_input.value and page_input.value.isdigit() else page_number}')
                                    ).props('flat color=green-5 dense')

                                # Page navigation buttons
                                with ui.row().classes('w-full justify-center gap-2 mt-2'):
                                    ui.button(
                                        'Previous',
                                        on_click=lambda: ui.navigate.to(
                                            f'/pdf-preview?file={file_path}&page={max(1, page_number - 1)}')
                                    ).props('flat color=blue-5')
                                    ui.button(
                                        'Next',
                                        on_click=lambda: ui.navigate.to(
                                            f'/pdf-preview?file={file_path}&page={page_number + 1}')
                                    ).props('flat color=blue-5')

                        if not objects:
                            create_empty_state('No objects found on this page')
                        else:
                            # Separate errors from other objects
                            errors = [
                                obj for obj in objects if isinstance(obj, PageError)]
                            other_objects = [
                                obj for obj in objects if not isinstance(obj, PageError)]

                            # Display errors section if any
                            if errors:
                                with create_collapsible_section('error', f'Errors ({len(errors)})', default_open=True):
                                    with ui.column().classes('gap-2 p-3'):
                                        for error in errors:
                                            styles = "bg-red-700 border-red-500"
                                            match error.error_type:
                                                case ErrorType.INFO:
                                                    styles = "bg-blue-700 border-blue-500"
                                                case ErrorType.WARNING:
                                                    styles = "bg-orange-700 border-orange-500"
                                                case _:
                                                    styles = "bg-red-700 border-red-500"
                                            with ui.card().classes(f'w-full {styles} border p-2'):
                                                ui.label(f'{error.error_type.value}: {error.message}').classes(
                                                    'text-sm text-white')

                            if not other_objects:
                                if not errors:
                                    create_empty_state(
                                        'No objects found on this page')
                            else:
                                ui.label(f'Found {len(other_objects)} object(s)').classes(
                                    'text-sm text-gray-300 my-4')

                                # Group objects by type
                                from collections import defaultdict
                                grouped = defaultdict(list)

                                for obj in other_objects:
                                    obj_type = type(obj).__name__
                                    grouped[obj_type].append(obj)

                                # Display grouped objects in collapsible sections
                                for obj_type, obj_list in grouped.items():
                                    with create_collapsible_section('category', f'{obj_type} ({len(obj_list)})', default_open=True):
                                        with ui.column().classes('gap-2 p-3'):
                                            for obj in obj_list:
                                                with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-2 hover:bg-gray-500 cursor-pointer transition-colors'):
                                                    # Display object info based on type
                                                    if hasattr(obj, 'tag'):
                                                        ui.label(f'Tag: {obj.tag.tag_str}').classes(
                                                            'text-sm font-mono break-all text-gray-200')
                                                    if hasattr(obj, 'src') and hasattr(obj, 'dest'):
                                                        src_tag = obj.src.tag.tag_str if obj.src else 'N/A'
                                                        dest_tag = obj.dest.tag.tag_str if obj.dest else 'N/A'
                                                        ui.label(f'{src_tag} → {dest_tag}').classes(
                                                            'text-sm break-all text-gray-200')
                                                    if hasattr(obj, 'get_guid'):
                                                        ui.label(f'GUID: {obj.get_guid()}...').classes(
                                                            'text-xs text-gray-400')

                # Initial load of object panel
                update_object_panel()
