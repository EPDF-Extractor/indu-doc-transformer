import base64
from collections import defaultdict
from nicegui import ui
from gui.global_state import ClientState
from gui.detail_panel_components import create_empty_state, create_collapsible_section
from indu_doc.plugins.eplan_pdfs.common_page_utils import PageError, ErrorType
from indu_doc.attributes import PDFLocationAttribute
import pymupdf

def render_pdf_page_with_highlights(page: pymupdf.Page, selected_bboxes: list[tuple[float, float, float, float]]) -> str:
    """Render a PDF page with red rectangles highlighting selected areas.
    
    Args:
        page: PyMuPDF page object
        selected_bboxes: List of bounding boxes (x0, y0, x1, y1) to highlight
        
    Returns:
        Base64 encoded PNG image data URL
    """
    print(f"[DEBUG] render_pdf_page_with_highlights called with {len(selected_bboxes)} bboxes")
    print(f"[DEBUG] Bboxes: {selected_bboxes}")
    
    # Get the pixmap at 150 DPI
    pix = page.get_pixmap(dpi=150)
    
    # Convert to PIL Image for drawing
    from PIL import Image, ImageDraw
    import io
    
    # Create PIL Image from pixmap
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    
    print(f"[DEBUG] Image size: {pix.width}x{pix.height}")
    print(f"[DEBUG] Page rect: {page.rect.width}x{page.rect.height}")
    
    # Draw rectangles on the image
    if selected_bboxes:
        draw = ImageDraw.Draw(img)
        
        # Calculate scaling factor from PDF coordinates to image coordinates
        scale_x = pix.width / page.rect.width
        scale_y = pix.height / page.rect.height
        
        for bbox in selected_bboxes:
            x0, y0, x1, y1 = bbox
            # Convert PDF coordinates to image coordinates
            img_x0 = x0 * scale_x
            img_y0 = y0 * scale_y
            img_x1 = x1 * scale_x
            img_y1 = y1 * scale_y
            
            print(f"[DEBUG] Drawing rect: PDF coords {bbox} -> Image coords ({img_x0}, {img_y0}, {img_x1}, {img_y1})")
            
            # Draw red rectangle with 2px width
            draw.rectangle(
                [(img_x0, img_y0), (img_x1, img_y1)],
                outline='red',
                width=4
            )
    
    # Convert back to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_data = buffer.getvalue()
    img_base64 = base64.b64encode(img_data).decode('utf-8')
    
    return f'data:image/png;base64,{img_base64}'

def create_pdf_preview_page(state: ClientState, file_path: str = '', page_number: int = 1):
    """Create a PDF preview page with navigation and object details."""
    
    # Track selected objects for highlighting
    selected_objects = set()
    
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

    # Cache the PDF document to avoid reopening on every page change
    if state.current_file_path != file_path:
        if state.current_doc:
            state.current_doc.close()
        try:
            state.current_doc = pymupdf.open(file_path)
            state.current_file_path = file_path
        except Exception as e:
            with ui.card().classes('w-full h-screen flex items-center justify-center bg-gray-900 border-2 border-gray-700'):
                ui.label(f'Error opening PDF: {str(e)}').classes('text-red-400 text-xl font-semibold')
            return

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
            with ui.splitter(horizontal=False, value=80, limits=(40.0, 90.0)).classes('w-full h-full') as splitter:
                with splitter.before:
                    # PDF viewer (left side)
                    pdf_container = ui.column().classes('w-full h-full p-4')
                    with pdf_container:
                        # PDF image container
                        pdf_image_div = ui.element('div').classes('w-full h-full flex items-center justify-center overflow-auto')
                        
                    def render_pdf_with_selected_highlights():
                        """Render PDF page with highlights for selected objects."""
                        print(f"[DEBUG] render_pdf_with_selected_highlights called")
                        print(f"[DEBUG] selected_objects: {selected_objects}")
                        pdf_image_div.clear()
                        with pdf_image_div:
                            try:
                                doc = state.current_doc
                                if not doc:
                                    raise ValueError("No document loaded.")
                                if not (1 <= page_number <= len(doc)):
                                    raise ValueError(f"Page {page_number} is out of range.")
                                
                                page = doc[page_number - 1]
                                
                                # Collect bboxes from selected objects
                                selected_bboxes = []
                                print(f"[DEBUG] Processing {len(selected_objects)} selected objects")
                                for obj_id in selected_objects:
                                    # Find the object and get its bbox
                                    print(f"[DEBUG] Looking for object with guid: {obj_id}")
                                    objects = state.manager.get_objects_on_page(page_number, file_path)
                                    print(f"[DEBUG] Found {len(objects)} objects on page")
                                    for obj in objects:
                                        if hasattr(obj, 'get_guid') and obj.get_guid() == obj_id:
                                            print(f"[DEBUG] Found matching object: {obj}")
                                            # Find PDFLocationAttribute
                                            if hasattr(obj, 'attributes'):
                                                print(f"[DEBUG] Object has {len(obj.attributes) if obj.attributes else 0} attributes")
                                                for attr in obj.attributes:
                                                    print(f"[DEBUG] Checking attribute: {type(attr).__name__}")
                                                    if isinstance(attr, PDFLocationAttribute):
                                                        print(f"[DEBUG] Found PDFLocationAttribute: page={attr.page_no}, bbox={attr.bbox}")
                                                        if attr.page_no + 1 == page_number:  # page_no is 0-based
                                                            selected_bboxes.append(attr.bbox)
                                                            print(f"[DEBUG] Added bbox to selected_bboxes")
                                            break
                                
                                # Render page with highlights
                                print(f"[DEBUG] Final selected_bboxes count: {len(selected_bboxes)}")
                                img_source = render_pdf_page_with_highlights(page, selected_bboxes)
                                ui.image(source=img_source)
                                
                            except Exception as e:
                                ui.label(f'Error rendering page: {str(e)}').classes('text-red-500 text-xl')
                    
                    # Initial render
                    render_pdf_with_selected_highlights()

                with splitter.after:
                    # Object panel (right side)
                    object_panel = ui.column().classes(
                        'w-full h-full border-2 border-gray-600 rounded-lg p-4 overflow-y-auto bg-gray-800')

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

                            # File and page info
                            with ui.column().classes('w-full gap-2 bg-gray-700 rounded-lg mb-4 p-4'):
                                ui.label(f'File: {file_name}').classes(
                                    'text-sm text-gray-200')

                                with ui.row().classes('w-full gap-2 items-center'):
                                    ui.label('Page:').classes(
                                        'text-sm text-gray-300 flex-shrink-0')
                                    page_input = ui.input(
                                        value=str(page_number),
                                        placeholder='Page number'
                                    ).classes('flex-grow').props('dark outlined dense type=number min=1')
                                    ui.button(
                                        'Go to',
                                        on_click=lambda: ui.navigate.to(
                                            f'/pdf-preview?file={file_path}&page={max(1, int(page_input.value)) if page_input.value and page_input.value.isdigit() else page_number}')
                                    ).classes('flex-shrink-0').props('flat color=green-5 dense')

                                with ui.row().classes('w-full gap-2'):
                                    ui.button(
                                        'Previous',
                                        on_click=lambda: ui.navigate.to(
                                            f'/pdf-preview?file={file_path}&page={max(1, page_number - 1)}')
                                    ).classes('flex-1').props('flat color=blue-5')
                                    ui.button(
                                        'Next',
                                        on_click=lambda: ui.navigate.to(
                                            f'/pdf-preview?file={file_path}&page={page_number + 1}')
                                    ).classes('flex-1').props('flat color=blue-5')

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
                                                if error.error_type == ErrorType.INFO:
                                                    styles = "bg-blue-700 border-blue-500"
                                                elif error.error_type == ErrorType.WARNING:
                                                    styles = "bg-orange-700 border-orange-500"
                                                else:
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
                                    grouped = defaultdict(list)

                                    for obj in other_objects:
                                        obj_type = type(obj).__name__
                                        grouped[obj_type].append(obj)

                                    # Display grouped objects in collapsible sections
                                    for obj_type, obj_list in grouped.items():
                                        with create_collapsible_section('category', f'{obj_type} ({len(obj_list)})', default_open=True):
                                            with ui.column().classes('gap-2 p-3'):
                                                for obj in obj_list:
                                                    # Check if object has location attribute
                                                    has_location = False
                                                    obj_guid = None
                                                    if hasattr(obj, 'get_guid'):
                                                        obj_guid = obj.get_guid()
                                                    
                                                    print(f"[DEBUG] Checking object: guid={obj_guid}, type={type(obj).__name__}")
                                                    
                                                    if hasattr(obj, 'attributes'):
                                                        print(f"[DEBUG] Object has attributes: {len(obj.attributes) if obj.attributes else 0}")
                                                        for attr in obj.attributes:
                                                            if isinstance(attr, PDFLocationAttribute):
                                                                print(f"[DEBUG] Found PDFLocationAttribute on page {attr.page_no}, current page {page_number}")
                                                                if attr.page_no + 1 == page_number:
                                                                    has_location = True
                                                                    print(f"[DEBUG] Object has location on current page!")
                                                                    break
                                                    
                                                    with ui.card().classes('w-full bg-gray-600 border border-gray-500 p-2 hover:bg-gray-500 transition-colors'):
                                                        with ui.row().classes('w-full items-start gap-2'):
                                                            # Add checkbox if object has location
                                                            if has_location and obj_guid:
                                                                def make_toggle_handler(guid):
                                                                    def handler(e):
                                                                        print(f"[DEBUG] Checkbox toggled for {guid}: {e.value}")
                                                                        if e.value:
                                                                            selected_objects.add(guid)
                                                                        else:
                                                                            selected_objects.discard(guid)
                                                                        print(f"[DEBUG] selected_objects now: {selected_objects}")
                                                                        render_pdf_with_selected_highlights()
                                                                    return handler
                                                                
                                                                print(f"[DEBUG] Creating checkbox for object {obj_guid}")
                                                                ui.checkbox(value=obj_guid in selected_objects).classes('flex-shrink-0').props('dense color=red').on_value_change(
                                                                    make_toggle_handler(obj_guid)
                                                                ).tooltip('Highlight on PDF')
                                                            
                                                            # Object info column
                                                            with ui.column().classes('flex-grow gap-1'):
                                                                # Display object info based on type
                                                                if hasattr(obj, 'tag'):
                                                                    ui.label(f'Tag: {obj.tag.tag_str}').classes(
                                                                        'text-sm font-mono break-all text-gray-200')
                                                                if hasattr(obj, 'src') and hasattr(obj, 'dest'):
                                                                    src_tag = obj.src.tag.tag_str if obj.src else 'N/A'
                                                                    dest_tag = obj.dest.tag.tag_str if obj.dest else 'N/A'
                                                                    ui.label(f'{src_tag} → {dest_tag}').classes(
                                                                        'text-sm break-all text-gray-200')
                                                                if obj_guid:
                                                                    ui.label(f'GUID: {obj_guid[:8]}...').classes(
                                                                        'text-xs text-gray-400')

                    # Initial load of object panel
                    update_object_panel()