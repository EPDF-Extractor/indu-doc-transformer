"""
Additional tests to improve coverage of the God factory class.

This module focuses on edge cases and less commonly used functionality
to achieve better test coverage.
"""

import pytest
from typing import OrderedDict
from unittest.mock import MagicMock, patch

from indu_doc.god import God, PagesObjectsMapper, PageMapperEntry
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.attributes import AttributeType
from indu_doc.xtarget import XTargetType
from indu_doc.connection import Connection


@pytest.fixture
def test_config():
    """Fixture providing a test AspectsConfig for God tests."""
    return AspectsConfig(
        OrderedDict(
            {
                "=": LevelConfig(Separator="=", Aspect="Functional"),
                "+": LevelConfig(Separator="+", Aspect="Location"),
                "-": LevelConfig(Separator="-", Aspect="Product"),
                ":": LevelConfig(Separator=":", Aspect="Pins"),
            }
        )
    )


@pytest.fixture
def god_instance(test_config):
    """Fixture providing a God instance for testing."""
    return God(test_config)


class TestPagesObjectsMapper:
    """Test the PagesObjectsMapper class."""

    def test_mapper_initialization(self):
        """Test PagesObjectsMapper initializes empty dictionaries."""
        mapper = PagesObjectsMapper()

        assert isinstance(mapper.page_to_objects, dict)
        assert isinstance(mapper.object_to_pages, dict)
        assert len(mapper.page_to_objects) == 0
        assert len(mapper.object_to_pages) == 0

    def test_add_mapping_with_page_number_none(self, god_instance, mock_page_info_no_footer):
        """Test adding mapping when page.number is None."""
        # Create a page info with None page number
        mock_page = MagicMock()
        mock_page.number = None
        mock_page.parent.name = "test.pdf"

        from indu_doc.common_page_utils import PageInfo, PageType
        page_info = PageInfo(
            page=mock_page,
            page_footer=mock_page_info_no_footer.page_footer,
            page_type=PageType.CONNECTION_LIST
        )

        # Create an xtarget which will call add_mapping
        xtarget = god_instance.create_xtarget(
            "=DEVICE", page_info, XTargetType.DEVICE)

        # Verify the mapping was created with -1 as page number
        pages = god_instance.get_pages_of_object(xtarget)
        assert len(pages) == 1
        entry = list(pages)[0]
        assert entry.page_number == -1

    def test_add_mapping_with_parent_none(self, god_instance, mock_page_info_no_footer):
        """Test adding mapping when page.parent is None."""
        # Create a page info with None parent
        mock_page = MagicMock()
        mock_page.number = 5
        mock_page.parent = None

        from indu_doc.common_page_utils import PageInfo, PageType
        page_info = PageInfo(
            page=mock_page,
            page_footer=mock_page_info_no_footer.page_footer,
            page_type=PageType.CONNECTION_LIST
        )

        # Create an xtarget which will call add_mapping
        xtarget = god_instance.create_xtarget(
            "=DEVICE", page_info, XTargetType.DEVICE)

        # Verify the mapping was created with "unknown" as file path
        pages = god_instance.get_pages_of_object(xtarget)
        assert len(pages) == 1
        entry = list(pages)[0]
        assert entry.file_path == "unknown"

    def test_get_objects_on_page(self, god_instance):
        """Test retrieving objects from a specific page."""
        # Create a consistent page info
        from indu_doc.common_page_utils import PageInfo, PageType
        from indu_doc.footers import PageFooter
        from unittest.mock import MagicMock

        # Create a mock page with stable values
        mock_page = MagicMock()
        mock_page.number = 5
        mock_page.parent = MagicMock()
        mock_page.parent.name = "test.pdf"

        page_info = PageInfo(
            page=mock_page,
            page_footer=PageFooter(project_name="Test",
                                   product_name="Test", tags=[]),
            page_type=PageType.CONNECTION_LIST
        )

        # Create several objects on this page
        xtarget1 = god_instance.create_xtarget(
            "=DEV1", page_info, XTargetType.DEVICE)
        xtarget2 = god_instance.create_xtarget(
            "=DEV2", page_info, XTargetType.DEVICE)
        connection = god_instance.create_connection(
            None, "=DEV1", "=DEV2", page_info)

        # Get objects on the page (mapper stores page.number + 1)
        page_num = 6  # mock_page.number + 1
        file_path = "test.pdf"
        objects = god_instance.get_objects_on_page(page_num, file_path)

        # Should include the two xtargets
        assert len(objects) >= 2  # At least DEV1 and DEV2
        assert xtarget1 in objects
        assert xtarget2 in objects

    def test_get_objects_on_nonexistent_page(self, god_instance):
        """Test retrieving objects from a page that doesn't exist."""
        objects = god_instance.get_objects_on_page(999, "nonexistent.pdf")

        assert isinstance(objects, set)
        assert len(objects) == 0

    def test_get_pages_of_object_by_string_xtarget(self, god_instance, mock_page_info_no_footer):
        """Test getting pages by xtarget GUID string."""
        xtarget = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)
        guid = xtarget.get_guid()

        # Get pages using the GUID string
        pages = god_instance.get_pages_of_object(guid)

        assert len(pages) == 1

    def test_get_pages_of_object_by_string_connection(self, god_instance, mock_page_info_no_footer):
        """Test getting pages by connection GUID string."""
        connection = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)
        guid = connection.get_guid()

        # Get pages using the GUID string
        pages = god_instance.get_pages_of_object(guid)

        assert len(pages) == 1

    def test_get_pages_of_object_by_string_link(self, god_instance, mock_page_info_no_footer):
        """Test getting pages by link GUID string."""
        link = god_instance.create_link("TEST_LINK", mock_page_info_no_footer)
        guid = link.get_guid()

        # Get pages using the GUID string
        pages = god_instance.get_pages_of_object(guid)

        assert len(pages) == 1

    def test_get_pages_of_nonexistent_object_string(self, god_instance):
        """Test getting pages of an object that doesn't exist (by string)."""
        pages = god_instance.get_pages_of_object("nonexistent-guid")

        assert isinstance(pages, set)
        assert len(pages) == 0


class TestTagCreationFailure:
    """Test tag creation failure scenarios."""

    def test_create_tag_returns_none_on_failure(self, god_instance, mock_page_info_no_footer):
        """Test that create_tag returns None when Tag creation fails."""
        # Mock Tag creation to return None
        with patch('indu_doc.god.Tag') as mock_tag_class:
            mock_tag_class.return_value = None
            mock_tag_class.get_tag_with_footer.return_value = None

            tag = god_instance.create_tag("=DEVICE", mock_page_info_no_footer)

            assert tag is None


class TestXTargetCreationFailure:
    """Test xtarget creation failure scenarios."""

    def test_create_xtarget_fails_when_tag_creation_fails(self, god_instance, mock_page_info_no_footer):
        """Test that create_xtarget returns None when tag creation fails."""
        # Mock create_tag to return None
        with patch.object(god_instance, 'create_tag', return_value=None):
            xtarget = god_instance.create_xtarget(
                "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)

            assert xtarget is None


class TestPinCreationFailure:
    """Test pin creation failure scenarios."""

    def test_create_pin_with_empty_pin_name(self, god_instance):
        """Test creating pin with empty pin name in the chain."""
        # This would test the TODO: what if pin name is empty?
        # A tag like "=DEVICE::" would have empty pin names
        pin = god_instance.create_pin("=DEVICE::")

        # Current implementation will create a pin with empty name
        # This tests the edge case mentioned in the TODO
        assert pin is not None
        assert pin.name == ""

    def test_create_pin_returns_none_impossible_case(self, god_instance):
        """Test the impossible case where current_pin is None after loop."""
        # This tests line 179-180 which checks if current_pin is None
        # This should be impossible with the current implementation but we test it

        # The only way current_pin could be None is if pins_names is empty,
        # but that's caught earlier. This is a defensive check.
        pin = god_instance.create_pin("=DEVICE")
        assert pin is None  # No pins in the tag


class TestMultiplePageMappings:
    """Test objects appearing on multiple pages."""

    def test_xtarget_on_multiple_pages(self, god_instance, mock_page_info_no_footer):
        """Test that an xtarget can be mapped to multiple pages."""
        # Create xtarget on first page
        xtarget1 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)

        # Create another page info
        mock_page2 = MagicMock()
        mock_page2.number = 5
        mock_page2.parent.name = "test2.pdf"

        from indu_doc.common_page_utils import PageInfo, PageType
        page_info2 = PageInfo(
            page=mock_page2,
            page_footer=mock_page_info_no_footer.page_footer,
            page_type=PageType.CONNECTION_LIST
        )

        # Reference the same xtarget on second page
        xtarget2 = god_instance.create_xtarget(
            "=DEVICE", page_info2, XTargetType.DEVICE)

        # Should be the same object
        assert xtarget1 is xtarget2

        # But should be on both pages
        pages = god_instance.get_pages_of_object(xtarget1)
        assert len(pages) == 2

    def test_connection_on_multiple_pages(self, god_instance, mock_page_info_no_footer):
        """Test that a connection can be mapped to multiple pages."""
        # Create connection on first page
        conn1 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)

        # Create another page info
        mock_page2 = MagicMock()
        mock_page2.number = 3
        mock_page2.parent.name = "test2.pdf"

        from indu_doc.common_page_utils import PageInfo, PageType
        page_info2 = PageInfo(
            page=mock_page2,
            page_footer=mock_page_info_no_footer.page_footer,
            page_type=PageType.CONNECTION_LIST
        )

        # Reference the same connection on second page
        conn2 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", page_info2)

        # Should be the same object
        assert conn1 is conn2

        # But should be on both pages
        pages = god_instance.get_pages_of_object(conn1)
        assert len(pages) == 2


class TestPageMapperEntry:
    """Test the PageMapperEntry dataclass."""

    def test_page_mapper_entry_creation(self):
        """Test creating a PageMapperEntry."""
        entry = PageMapperEntry(page_number=5, file_path="test.pdf")

        assert entry.page_number == 5
        assert entry.file_path == "test.pdf"

    def test_page_mapper_entry_hashable(self):
        """Test that PageMapperEntry is hashable and can be used in sets/dicts."""
        entry1 = PageMapperEntry(page_number=5, file_path="test.pdf")
        entry2 = PageMapperEntry(page_number=5, file_path="test.pdf")
        entry3 = PageMapperEntry(page_number=6, file_path="test.pdf")

        # Same entries should have same hash
        assert hash(entry1) == hash(entry2)

        # Different entries should (usually) have different hash
        assert hash(entry1) != hash(entry3)

        # Can be used in a set
        entry_set = {entry1, entry2, entry3}
        assert len(entry_set) == 2  # entry1 and entry2 are the same

    def test_page_mapper_entry_equality(self):
        """Test PageMapperEntry equality."""
        entry1 = PageMapperEntry(page_number=5, file_path="test.pdf")
        entry2 = PageMapperEntry(page_number=5, file_path="test.pdf")
        entry3 = PageMapperEntry(page_number=6, file_path="test.pdf")

        assert entry1 == entry2
        assert entry1 != entry3


class TestGodEdgeCasesAdditional:
    """Additional edge case tests for God class."""

    def test_create_connection_with_link_and_multiple_attributes(self, god_instance, mock_page_info_no_footer):
        """Test connection with link and multiple attributes."""
        attr1 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        attr2 = god_instance.create_attribute(
            AttributeType.SIMPLE, "size", "large")

        connection = god_instance.create_connection_with_link(
            "=CABLE", "=DEV1:PIN1", "=DEV2:PIN2", mock_page_info_no_footer, (
                attr1, attr2)
        )

        assert connection is not None
        assert len(connection.links) == 1
        link = connection.links[0]
        assert attr1 in link.attributes
        assert attr2 in link.attributes

    def test_create_link_without_pins_or_parent(self, god_instance, mock_page_info_no_footer):
        """Test creating a standalone link without pins or parent."""
        link = god_instance.create_link(
            "STANDALONE_LINK", mock_page_info_no_footer)

        assert link is not None
        assert link.name == "STANDALONE_LINK"
        assert link.src_pin is None
        assert link.dest_pin is None
        assert link.parent is None

    def test_create_multiple_different_xtargets(self, god_instance, mock_page_info_no_footer):
        """Test creating multiple different xtargets of different types."""
        device = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)
        cable = god_instance.create_xtarget(
            "=CABLE", mock_page_info_no_footer, XTargetType.CABLE)
        other = god_instance.create_xtarget(
            "=OTHER", mock_page_info_no_footer, XTargetType.OTHER)

        assert device.target_type == XTargetType.DEVICE
        assert cable.target_type == XTargetType.CABLE
        assert other.target_type == XTargetType.OTHER

        assert len(god_instance.xtargets) == 3

    def test_pin_chain_with_multiple_levels(self, god_instance):
        """Test creating a deep pin chain."""
        pin = god_instance.create_pin("=DEVICE:L1:L2:L3:L4:L5")

        assert pin.name == "L1"
        assert pin.child.name == "L2"
        assert pin.child.child.name == "L3"
        assert pin.child.child.child.name == "L4"
        assert pin.child.child.child.child.name == "L5"
        assert pin.child.child.child.child.child is None

    def test_connection_virtual_cable_no_through(self, god_instance, mock_page_info_no_footer):
        """Test that virtual cable connections have no through."""
        connection = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)

        assert connection.through is None
        assert connection.src is not None
        assert connection.dest is not None
