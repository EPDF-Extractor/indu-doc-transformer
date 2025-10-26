import pytest
import os
import tempfile
from indu_doc.god import God
from indu_doc.configs import AspectsConfig
from indu_doc.attributes import AttributeType
from indu_doc.db import save_to_db, load_from_db
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
    # Save to database
    save_to_db(sample_god, temp_db_file)
    
    # Load from database
    loaded_god = load_from_db(temp_db_file)
    
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
    loaded_god = load_from_db(temp_db_file)
    
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
    loaded_god = load_from_db(temp_db_file)
    
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
    config_list = [{"Aspect": "Functional", "Separator": "="}]
    configs = AspectsConfig.init_from_list(config_list)
    god = God(configs)
    
    # Save and load empty god
    save_to_db(god, temp_db_file)
    loaded_god = load_from_db(temp_db_file)
    
    # Verify it's empty
    assert len(loaded_god.xtargets) == 0
    assert len(loaded_god.connections) == 0
    assert len(loaded_god.attributes) == 0
    assert loaded_god.configs == god.configs


def test_pin_hierarchy_preservation(temp_db_file, temp_pdf_file):
    """Test that pin child hierarchy is preserved when saving and loading."""
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
    loaded_god = load_from_db(temp_db_file)
    
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
