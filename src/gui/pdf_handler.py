from typing import List
from nicegui import ui
import tempfile
import os
import re
from gui.global_state import manager, aspects, config_dialog_handler, uploaded_pdfs


def _extract_pdf_filename_from_key(key: str) -> str | None:
    """Extract the real PDF filename from NiceGUI's internal __key value."""
    basenames = {os.path.basename(p) for p in uploaded_pdfs}

    # Pattern: optional leading digits, filename, optional trailing digits
    m = re.match(r'^\d*([A-Za-z0-9_\- ().]+\.pdf)\d*$', key, re.IGNORECASE)
    if m:
        cand = m.group(1)
        if not basenames or cand in basenames:
            return cand
        # Try trimming leading digits inside candidate (safety)
        trimmed = re.sub(r'^\d+', '', cand)
        if trimmed in basenames:
            return trimmed

    # Fallback: find all .pdf substrings
    matches = re.findall(r'([A-Za-z0-9_\- ().]+\.pdf)', key, re.IGNORECASE)
    if matches:
        # Prefer one that matches tracked basenames
        for cand in matches:
            if cand in basenames:
                return cand
        # Also try trimming leading digits for each
        for cand in matches:
            trimmed = re.sub(r'^\d+', '', cand)
            if trimmed in basenames:
                return trimmed
        # Otherwise return the last (often the actual filename before trailing digits)
        return matches[-1]
    return None


def create_pdf_picker():
    """Create the PDF list section."""

    with ui.card().classes('flex-grow min-w-0 flex margin-0 p-0 bg-gray-800 border-2 border-gray-600'):
        up = ui.upload(
            on_upload=lambda e: handle_pdf_upload(e),
            auto_upload=True,
            multiple=False,
        ).props('dark accept=.pdf color=blue-5 label="Upload PDF" style="height:12rem; overflow:auto;"').classes('w-full')
        up.on('removed', lambda e: handle_pdf_removal(e))


def handle_pdf_removal(e):
    print("Removal event raw object:", e)
    print("Removal event args:", getattr(e, 'args', None))
    """Handle PDF file removal."""
    filename = None

    # 1. If future NiceGUI adds e.name
    if hasattr(e, 'name'):
        filename = getattr(e, 'name')

    # 2. Inspect args for dicts with __key
    if not filename and getattr(e, 'args', None):
        for item in e.args:
            if isinstance(item, dict):
                key = item.get('__key') or ''
                extracted = _extract_pdf_filename_from_key(key)
                if extracted:
                    filename = extracted
                    print(f"Extracted filename from __key: {filename}")
                    break

    # 3. Fallback: if exactly one tracked file, assume that one
    if not filename and len(uploaded_pdfs) == 1:
        filename = os.path.basename(uploaded_pdfs[0])
        print(f"Fallback to sole tracked file: {filename}")

    # 4. Last resort: try to find any temp file whose basename appears (without digits) in keys
    if not filename and getattr(e, 'args', None):
        stripped_keys = []
        for item in e.args:
            if isinstance(item, dict):
                k = item.get('__key', '')
                # remove leading digits and trailing digits
                core = re.sub(r'^\d+', '', k)
                core = re.sub(r'\d+$', '', core)
                stripped_keys.append(core.lower())
        for path in uploaded_pdfs:
            bn = os.path.basename(path).lower()
            if any(bn in sk for sk in stripped_keys):
                filename = os.path.basename(path)
                print(f"Inferred by matching core key parts: {filename}")
                break

    if not filename:
        ui.notify('Could not determine removed filename; clearing tracked uploads')
        # As a safety measure (single-file mode), purge all
        for path in list(uploaded_pdfs):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as ex:
                    print(f"Error deleting (bulk fallback) {path}: {ex}")
            uploaded_pdfs.remove(path)
        return

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)
    print(f"Resolved removal file path: {file_path}")

    # Match by basename if absolute path not stored identically (robustness)
    matched_path = None
    if file_path in uploaded_pdfs:
        matched_path = file_path
    else:
        # Try basename matching
        for p in uploaded_pdfs:
            if os.path.basename(p) == filename:
                matched_path = p
                break

    if not matched_path:
        ui.notify(f'{filename} not found in tracked list')
        return

    uploaded_pdfs.remove(matched_path)
    if os.path.exists(matched_path):
        try:
            os.remove(matched_path)
        except OSError as ex:
            ui.notify(f'Error deleting {filename}: {ex}')
            return
    ui.notify(f'Removed {filename}')


def handle_pdf_upload(e):
    """Handle PDF file upload."""
    if e.content:
        print(f"Uploading file: {e.name}")
        filename = e.name
        if filename.lower().endswith('.pdf'):
            # Save uploaded file to temp directory and store the path
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, filename)

            with open(file_path, 'wb') as f:
                f.write(e.content.read())

            if file_path not in uploaded_pdfs:
                uploaded_pdfs.append(file_path)
                ui.notify(f'Uploaded {filename}')
            else:
                ui.notify(f'{filename} already exists')
        else:
            ui.notify('Please upload a PDF file')
    else:
        ui.notify('No file selected')
