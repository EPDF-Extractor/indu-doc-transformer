import pytest
import os
import tempfile
from io import BytesIO
from indu_doc.god import God
from indu_doc.configs import AspectsConfig
from indu_doc.attributes import AttributeType
from indu_doc.exporters.db_builder.db import save_to_db, load_from_db
from indu_doc.exporters.db_builder.db_exporter import SQLITEDBExporter
from unittest.mock import MagicMock


@pytest.fixture
def temp_db_file():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.unlink(path)
        except PermissionError:
            pass  # File may be locked on Windows


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing."""
    fd, path = tempfile.mkstemp(suffix='.pdf')
    # Write minimal PDF content
    os.write(fd, b'%PDF-1.4\n%Test PDF\n%%EOF')
    os.close(fd)
    yield path
    if os.path.exists(path):
        try:
            os.unlink(path)
        except PermissionError:
            pass


@pytest.fixture
def mock_page_info(temp_pdf_file):
    """Create a mock PageInfo for testing."""
    page_info = MagicMock()
    page_info.page.number = 0  # 0-based, will be stored as 1
    page_info.page.parent.name = temp_pdf_file
    page_info.page_footer = None
    return page_info


@pytest.fixture
def sample_god(mock_page_info):
    """Create a sample God instance with some data."""
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
        {"Aspect": "Product Aspect", "Separator": "-"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create some XTargets
    god.create_xtarget("=A+B1-X1", mock_page_info)
    god.create_xtarget("=A+B2-X2", mock_page_info)
    
    # Create a connection
    god.create_connection(
        tag="=W1",
        tag_from="=A+B1-X1",
        tag_to="=A+B2-X2",
        page_info=mock_page_info
    )
    
    return god


def test_save_and_load_basic(temp_db_file, sample_god):
    """Test basic save and load functionality."""
    import tempfile
    
    # Save to database
    save_to_db(sample_god, temp_db_file)
    
    # Load from database with document extraction
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify configs
        assert loaded_god.configs == sample_god.configs
        
        # Verify XTargets
        assert len(loaded_god.xtargets) == len(sample_god.xtargets)
        for guid in sample_god.xtargets:
            assert guid in loaded_god.xtargets
            assert str(loaded_god.xtargets[guid].tag) == str(sample_god.xtargets[guid].tag)
            assert loaded_god.xtargets[guid].target_type == sample_god.xtargets[guid].target_type
        
        # Verify connections
        assert len(loaded_god.connections) == len(sample_god.connections)
        for guid in sample_god.connections:
            assert guid in loaded_god.connections


def test_save_and_load_with_attributes(temp_db_file, temp_pdf_file):
    """Test save and load with attributes."""
    import tempfile
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create XTarget with attributes
    attr = god.create_attribute(AttributeType.SIMPLE, "Color", "Red")
    god.create_xtarget("=A+B1", mock_page_info, attributes=(attr,))
    
    # Save and load
    save_to_db(god, temp_db_file)
    
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify attributes
        assert len(loaded_god.attributes) == len(god.attributes)
        
        # Verify XTarget has the attribute
        for xtarget in loaded_god.xtargets.values():
            assert len(xtarget.attributes) > 0
            attr_list = list(xtarget.attributes)
            assert attr_list[0].name == "Color"
            assert attr_list[0].get_value() == "Red"


def test_save_and_load_with_aspects(temp_db_file, temp_pdf_file):
    """Test save and load preserves tag aspects."""
    import tempfile
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
        {"Aspect": "Product", "Separator": "-"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create a tag with multiple aspects
    god.create_xtarget("=Motor+Room1-Device1", mock_page_info)
    
    # Save and load
    save_to_db(god, temp_db_file)
    
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify aspects are preserved
        for guid, xtarget in loaded_god.xtargets.items():
            original_xtarget = god.xtargets[guid]
            original_aspects = original_xtarget.tag.get_aspects()
            loaded_aspects = xtarget.tag.get_aspects()
            
            if original_aspects and loaded_aspects:
                assert len(original_aspects) == len(loaded_aspects)
                for sep in original_aspects:
                    assert sep in loaded_aspects
                    assert len(original_aspects[sep]) == len(loaded_aspects[sep])


def test_empty_god(temp_db_file):
    """Test save and load with an empty God instance."""
    import tempfile
    
    config_list = [{"Aspect": "Functional", "Separator": "="}]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Save and load empty god
    save_to_db(god, temp_db_file)
    
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify it's empty
        assert len(loaded_god.xtargets) == 0
        assert len(loaded_god.connections) == 0
        assert len(loaded_god.attributes) == 0
        assert loaded_god.configs == god.configs


def test_pin_hierarchy_preservation(temp_db_file, temp_pdf_file):
    """Test that pin child hierarchy is preserved when saving and loading."""
    import tempfile
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create XTargets
    god.create_xtarget("=DEVICE1+A1", mock_page_info)
    god.create_xtarget("=DEVICE2+A2", mock_page_info)
    
    # Create a connection with hierarchical pins (PIN1 -> PIN2 -> PIN3)
    connection = god.create_connection_with_link(
        "=CABLE",
        "=DEVICE1+A1:PIN1:PIN2:PIN3",
        "=DEVICE2+A2:PINX:PINY",
        mock_page_info
    )
    
    assert connection is not None
    assert len(connection.links) == 1
    
    link = connection.links[0]
    assert link.src_pin is not None
    assert link.dest_pin is not None
    
    # Verify source pin hierarchy
    src_pin = link.src_pin
    assert src_pin.name == "PIN1"
    assert src_pin.child is not None
    assert src_pin.child.name == "PIN2"
    assert src_pin.child.child is not None
    assert src_pin.child.child.name == "PIN3"
    assert src_pin.child.child.child is None
    
    # Verify dest pin hierarchy
    dest_pin = link.dest_pin
    assert dest_pin.name == "PINX"
    assert dest_pin.child is not None
    assert dest_pin.child.name == "PINY"
    assert dest_pin.child.child is None
    
    # Save to database
    save_to_db(god, temp_db_file)
    
    # Load from database
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify the connection and links exist
        assert len(loaded_god.connections) == len(god.connections)
        assert len(loaded_god.links) == len(god.links)
        # Note: loaded_god.pins will have more entries than god.pins because loading
        # adds all child pins to the dictionary, while god.create_pin only adds root pins
        
        # Find the loaded connection
        loaded_connection = None
        for conn in loaded_god.connections.values():
            if conn.get_guid() == connection.get_guid():
                loaded_connection = conn
                break
        
        assert loaded_connection is not None
        assert len(loaded_connection.links) == 1
        
        loaded_link = loaded_connection.links[0]
        assert loaded_link.src_pin is not None
        assert loaded_link.dest_pin is not None
        
        # Verify source pin hierarchy is preserved
        loaded_src_pin = loaded_link.src_pin
        assert loaded_src_pin.name == "PIN1"
        assert loaded_src_pin.child is not None
        assert loaded_src_pin.child.name == "PIN2"
        assert loaded_src_pin.child.child is not None
        assert loaded_src_pin.child.child.name == "PIN3"
        assert loaded_src_pin.child.child.child is None
        
        # Verify dest pin hierarchy is preserved
        loaded_dest_pin = loaded_link.dest_pin
        assert loaded_dest_pin.name == "PINX"
        assert loaded_dest_pin.child is not None
        assert loaded_dest_pin.child.name == "PINY"
        assert loaded_dest_pin.child.child is None
        
        # Verify pin GUIDs match
        assert loaded_src_pin.get_guid() == src_pin.get_guid()
        assert loaded_dest_pin.get_guid() == dest_pin.get_guid()
        
        # Verify all individual pins in the chain are in loaded_god.pins
        assert loaded_src_pin.get_guid() in loaded_god.pins
        assert loaded_src_pin.child.get_guid() in loaded_god.pins
        assert loaded_src_pin.child.child.get_guid() in loaded_god.pins
        assert loaded_dest_pin.get_guid() in loaded_god.pins
        assert loaded_dest_pin.child.get_guid() in loaded_god.pins


def test_document_extraction(temp_db_file, temp_pdf_file):
    """Test that documents can be extracted from the database."""
    import tempfile
    from indu_doc.exporters.db_builder.db import extract_documents_from_db
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create XTarget
    god.create_xtarget("=A+B1", mock_page_info)
    
    # Save to database
    save_to_db(god, temp_db_file)
    
    # Extract documents to a temporary directory
    with tempfile.TemporaryDirectory() as extract_dir:
        filename_to_path = extract_documents_from_db(temp_db_file, extract_dir)
        
        # Verify the document was extracted
        assert len(filename_to_path) == 1
        pdf_basename = os.path.basename(temp_pdf_file)
        assert pdf_basename in filename_to_path
        
        # Verify the file exists and has content
        extracted_path = filename_to_path[pdf_basename]
        assert os.path.exists(extracted_path)
        assert os.path.getsize(extracted_path) > 0


def test_load_with_document_extraction(temp_db_file, temp_pdf_file):
    """Test loading from database with document extraction."""
    import tempfile
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create XTarget
    xtarget = god.create_xtarget("=A+B1", mock_page_info)
    
    # Save to database
    save_to_db(god, temp_db_file)
    
    # Load with document extraction
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify XTargets were loaded
        assert len(loaded_god.xtargets) == 1
        
        # Verify the file paths in the mapper are absolute paths in the extract directory
        pdf_basename = os.path.basename(temp_pdf_file)
        extracted_path = os.path.join(extract_dir, pdf_basename)
        
        assert os.path.abspath(extracted_path) in loaded_god.pages_mapper.file_paths
        
        # Verify we can query objects using the new path
        objects = loaded_god.get_objects_on_page(1, extracted_path)
        assert len(objects) == 1
        loaded_xtarget = list(objects)[0]
        assert hasattr(loaded_xtarget, 'get_guid')
        assert loaded_xtarget.get_guid() == xtarget.get_guid()  # type: ignore


def test_load_without_document_extraction(temp_db_file, temp_pdf_file):
    """Test loading from database requires document extraction."""
    import tempfile
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create XTarget
    xtarget = god.create_xtarget("=A+B1", mock_page_info)
    
    # Save to database
    save_to_db(god, temp_db_file)
    
    # Load with document extraction (required)
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify XTargets were loaded
        assert len(loaded_god.xtargets) == 1
        
        # Verify the file paths in the mapper are absolute paths
        pdf_basename = os.path.basename(temp_pdf_file)
        extracted_path = os.path.join(extract_dir, pdf_basename)
        assert os.path.abspath(extracted_path) in loaded_god.pages_mapper.file_paths
        
        # Verify we can query objects using the absolute path
        objects = loaded_god.get_objects_on_page(1, extracted_path)
        assert len(objects) == 1
        loaded_xtarget = list(objects)[0]
        assert hasattr(loaded_xtarget, 'get_guid')
        assert loaded_xtarget.get_guid() == xtarget.get_guid()  # type: ignore
        
        # Verify we can also query using the absolute path
        objects2 = loaded_god.get_objects_on_page(1, os.path.abspath(extracted_path))
        assert len(objects2) == 1


def test_absolute_paths_validation(temp_db_file, temp_pdf_file):
    """Test that all paths in the loaded mapper are absolute."""
    import tempfile
    
    config_list = [
        {"Aspect": "Functional", "Separator": "="},
        {"Aspect": "Location", "Separator": "+"},
    ]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Create mock page_info
    mock_page_info = MagicMock()
    mock_page_info.page.number = 0
    mock_page_info.page.parent.name = temp_pdf_file
    mock_page_info.page_footer = None
    
    # Create XTarget
    god.create_xtarget("=A+B1", mock_page_info)
    
    # Save to database
    save_to_db(god, temp_db_file)
    
    # Load with document extraction
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = load_from_db(temp_db_file, extract_docs_to=extract_dir)
        
        # Verify all paths in file_paths are absolute
        for file_path in loaded_god.pages_mapper.file_paths:
            assert os.path.isabs(file_path), f"Path is not absolute: {file_path}"
        
        # Verify all paths in page entries are absolute
        for page_entry in loaded_god.pages_mapper.page_to_objects.keys():
            assert os.path.isabs(page_entry.file_path), f"Page entry path is not absolute: {page_entry.file_path}"


def test_db_exporter_export(temp_pdf_file):
    """Test SQLITEDBExporter.export_data()"""
    # Create a simple God instance
    configs = AspectsConfig.init_from_list([])
    god = God(configs)
    
    # Add a simple xtarget
    from indu_doc.xtarget import XTarget
    from indu_doc.tag import Tag
    
    tag = Tag("TestTag", configs)
    xtarget = XTarget(tag, configs)
    god.xtargets[xtarget.get_guid()] = xtarget
    
    # Export to BytesIO
    db_bytes = SQLITEDBExporter.export_data(god)
    
    # Verify it's a BytesIO object
    assert isinstance(db_bytes, BytesIO)
    
    # Verify it has content
    db_bytes.seek(0)
    content = db_bytes.read()
    assert len(content) > 0
    
    # Verify it's a valid SQLite database (starts with SQLite magic number)
    assert content[:16] == b'SQLite format 3\x00'


def test_db_exporter_roundtrip(temp_pdf_file):
    """Test export and import roundtrip with SQLITEDBExporter"""
    # Create a God instance with some data
    configs = AspectsConfig.init_from_list([])
    original_god = God(configs)
    
    from indu_doc.xtarget import XTarget, XTargetType
    from indu_doc.tag import Tag
    from indu_doc.connection import Connection
    from indu_doc.god import PageMapperEntry
    
    # Add xtargets
    tag1 = Tag("Device1", configs)
    xt1 = XTarget(tag1, configs, target_type=XTargetType.DEVICE)
    original_god.xtargets[xt1.get_guid()] = xt1
    
    tag2 = Tag("Device2", configs)
    xt2 = XTarget(tag2, configs, target_type=XTargetType.DEVICE)
    original_god.xtargets[xt2.get_guid()] = xt2
    
    # Add a connection
    conn = Connection(src=xt1, dest=xt2)
    original_god.connections[conn.get_guid()] = conn
    
    # Add page mapping
    page_entry = PageMapperEntry(page_number=1, file_path=os.path.abspath(temp_pdf_file))
    original_god.pages_mapper._file_paths.add(os.path.abspath(temp_pdf_file))
    original_god.pages_mapper.page_to_objects[page_entry].add(xt1)
    original_god.pages_mapper.object_to_pages[xt1].add(page_entry)
    
    # Export
    db_bytes = SQLITEDBExporter.export_data(original_god)
    
    # Import
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = SQLITEDBExporter.import_from_bytes(db_bytes, extract_dir)
        
        # Verify XTargets
        assert len(loaded_god.xtargets) == 2
        
        # Verify connections
        assert len(loaded_god.connections) == 1
        
        # Verify page mapper has absolute paths
        for file_path in loaded_god.pages_mapper.file_paths:
            assert os.path.isabs(file_path)


def test_db_exporter_import_from_file(temp_db_file, temp_pdf_file):
    """Test SQLITEDBExporter.import_from_file()"""
    # Create and save a God instance
    configs = AspectsConfig.init_from_list([])
    original_god = God(configs)
    
    from indu_doc.xtarget import XTarget
    from indu_doc.tag import Tag
    
    tag = Tag("TestDevice", configs)
    xtarget = XTarget(tag, configs)
    original_god.xtargets[xtarget.get_guid()] = xtarget
    
    # Save directly to file
    save_to_db(original_god, temp_db_file)
    
    # Import using the exporter
    with tempfile.TemporaryDirectory() as extract_dir:
        loaded_god = SQLITEDBExporter.import_from_file(temp_db_file, extract_dir)
        
        # Verify the data
        assert len(loaded_god.xtargets) == 1
        assert list(loaded_god.xtargets.values())[0].tag.tag_str == "TestDevice"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

