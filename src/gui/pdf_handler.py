from typing import List
from nicegui import ui


def create_pdf_picker(uploaded_pdfs: List[str]):
    """Create the PDF list section."""

    with ui.card().classes('flex-grow min-w-0 flex margin-0 p-0'):
        ui.upload(
            on_upload=lambda e: handle_pdf_upload(
                e, uploaded_pdfs),
            auto_upload=True,
            multiple=False,
        ).props('accept=.pdf color=primary label="Upload PDF" style="height:12rem; overflow:auto;"').classes('w-full')


def handle_pdf_upload(e, uploaded_pdfs: List[str]):
    """Handle PDF file upload."""
    if e.content:
        filename = e.name
        if filename.lower().endswith('.pdf'):
            if filename not in uploaded_pdfs:
                uploaded_pdfs.append(filename)
                ui.notify(f'Uploaded {filename}')
            else:
                ui.notify(f'{filename} already exists')
        else:
            ui.notify('Please upload a PDF file')
    else:
        ui.notify('No file selected')
