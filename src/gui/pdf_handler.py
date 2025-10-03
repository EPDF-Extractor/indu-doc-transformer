from typing import Optional
from nicegui import ui
import tempfile
import os
import re


def _extract_filename_from_key(key: str, uploaded_pdfs: list[str]) -> Optional[str]:
    """
    Extract PDF filename from NiceGUI's internal __key value.

    Strategy:
    1. Try to match pattern with optional digits around the filename
    2. Validate against known uploaded files
    3. Fallback to basename matching
    """
    if not key:
        return None

    basenames = {os.path.basename(p) for p in uploaded_pdfs}

    # Primary pattern: optional leading digits, filename, optional trailing digits
    match = re.match(r'^\d*([A-Za-z0-9_\- ().]+\.pdf)\d*$', key, re.IGNORECASE)
    if match:
        candidate = match.group(1)
        if candidate in basenames:
            return candidate

    # Fallback: find all .pdf substrings and match against basenames
    pdf_matches = re.findall(r'([A-Za-z0-9_\- ().]+\.pdf)', key, re.IGNORECASE)
    for candidate in pdf_matches:
        if candidate in basenames:
            return candidate

    return None


def _find_file_path(filename: str, uploaded_pdfs: list[str]) -> Optional[str]:
    """Find the full file path for a given filename from uploaded PDFs list."""
    if not filename:
        return None

    # Try exact match first
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    if file_path in uploaded_pdfs:
        return file_path

    # Try basename matching
    for path in uploaded_pdfs:
        if os.path.basename(path) == filename:
            return path

    return None


def _safe_remove_file(file_path: str) -> bool:
    """Safely remove a file from disk. Returns True if successful."""
    if not os.path.exists(file_path):
        return True

    try:
        os.remove(file_path)
        return True
    except OSError as e:
        print(f"Error deleting file {file_path}: {e}")
        return False


def _cleanup_invalid_paths(uploaded_pdfs: list[str]) -> None:
    """Remove paths from the list that no longer exist on disk."""
    invalid_paths = [
        path for path in uploaded_pdfs if not os.path.exists(path)]
    for path in invalid_paths:
        uploaded_pdfs.remove(path)
        print(f"Removed invalid path from state: {path}")


def create_pdf_picker(state):
    """Create the PDF upload component with removal handling."""
    from gui.global_state import ClientState

    if not isinstance(state, ClientState):
        raise TypeError("state must be a ClientState instance")

    # Clean up any invalid paths that might exist in state on init
    _cleanup_invalid_paths(state.uploaded_pdfs)

    # Notify user if there are pre-existing files
    if state.uploaded_pdfs:
        file_count = len(state.uploaded_pdfs)
        filenames = [os.path.basename(p) for p in state.uploaded_pdfs]
        ui.notify(
            f'Restored {file_count} existing file(s): {", ".join(filenames)}', color='info')

    with ui.card().classes('flex-grow min-w-0 flex margin-0 p-0 bg-gray-800 border-2 border-gray-600'):
        upload_component = ui.upload(
            on_upload=lambda e: handle_pdf_upload(e, state),
            auto_upload=True,
            multiple=False,
        ).props('dark accept=.pdf color=blue-5 label="Upload PDF" style="height:12rem; overflow:auto;"').classes('w-full')

        upload_component.on('removed', lambda e: handle_pdf_removal(e, state))

        # Add existing files to the upload component's display
        for file_path in state.uploaded_pdfs:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                # Simulate an upload event to display the file in the component
                upload_component.props(
                    f'model-value=[{{"name": "{filename}", "size": {os.path.getsize(file_path)}, "__status": "uploaded"}}]')


def handle_pdf_removal(e, state):
    """Handle PDF file removal event."""
    from gui.global_state import ClientState

    if not isinstance(state, ClientState):
        raise TypeError("state must be a ClientState instance")

    uploaded_pdfs = state.uploaded_pdfs

    print(f"Removal event - args: {getattr(e, 'args', None)}")

    filename = None

    # Check if event has direct name attribute (future NiceGUI versions)
    if hasattr(e, 'name'):
        filename = getattr(e, 'name')

    # Extract filename from __key in event args
    if not filename and getattr(e, 'args', None):
        for item in e.args:
            if isinstance(item, dict) and '__key' in item:
                key = item['__key']
                extracted = _extract_filename_from_key(key, uploaded_pdfs)
                if extracted:
                    filename = extracted
                    print(f"Extracted filename from __key: {filename}")
                    break

    # Fallback: if only one file is uploaded, assume it's the one being removed
    if not filename and len(uploaded_pdfs) == 1:
        filename = os.path.basename(uploaded_pdfs[0])
        print(f"Fallback to sole tracked file: {filename}")

    # Could not determine filename - clear all as safety measure (single-file mode)
    if not filename:
        ui.notify(
            'Could not determine removed file; clearing all uploads', color='warning')
        for path in list(uploaded_pdfs):
            _safe_remove_file(path)
        uploaded_pdfs.clear()
        return

    # Find and remove the file
    file_path = _find_file_path(filename, uploaded_pdfs)

    if not file_path:
        ui.notify(f'{filename} not found in tracked list', color='warning')
        return

    if _safe_remove_file(file_path):
        uploaded_pdfs.remove(file_path)
        ui.notify(f'Removed {filename}', color='positive')
    else:
        ui.notify(f'Error deleting {filename}', color='negative')


def handle_pdf_upload(e, state):
    """Handle PDF file upload event."""
    from gui.global_state import ClientState

    if not isinstance(state, ClientState):
        raise TypeError("state must be a ClientState instance")

    if not e.content:
        ui.notify('No file selected', color='warning')
        return

    filename = e.name
    print(f"Uploading file: {filename}")

    # Validate file type
    if not filename.lower().endswith('.pdf'):
        ui.notify('Please upload a PDF file', color='negative')
        return

    # Save to temp directory
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)

    try:
        with open(file_path, 'wb') as f:
            f.write(e.content.read())

        # Add to tracked list if not already present
        if file_path not in state.uploaded_pdfs:
            state.uploaded_pdfs.append(file_path)
            ui.notify(f'Uploaded {filename}', color='positive')
        else:
            ui.notify(f'{filename} already exists', color='info')

    except Exception as ex:
        ui.notify(f'Error uploading {filename}: {str(ex)}', color='negative')
        print(f"Upload error: {ex}")
