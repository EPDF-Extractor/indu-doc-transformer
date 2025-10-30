"""
Additional tests for God factory class to improve coverage.
Focuses on edge cases and error handling paths.
"""

import pytest
from typing import OrderedDict
from unittest.mock import patch, MagicMock

from indu_doc.god import God
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.attributes import AttributeType, SimpleAttribute
from indu_doc.xtarget import XTargetType
from indu_doc.connection import Connection, Link
from indu_doc.plugins.eplan_pdfs.common_page_utils import PageError, ErrorType


@pytest.fixture
def test_config():
    """Fixture providing a test AspectsConfig."""
    return AspectsConfig(
        OrderedDict({
            "=": LevelConfig(Separator="=", Aspect="Functional"),
            "+": LevelConfig(Separator="+", Aspect="Location"),
            "-": LevelConfig(Separator="-", Aspect="Product"),
            ":": LevelConfig(Separator=":", Aspect="Pins"),
        })
    )


@pytest.fixture
def god_instance(test_config):
    """Fixture providing a God instance."""
    return God(test_config)


class TestGodCreateAttribute:
    """Test create_attribute method."""

    def test_create_attribute_simple(self, god_instance):
        """Test creating a simple attribute."""
        attr = god_instance.create_attribute(AttributeType.SIMPLE, "color", "red")
        
        assert attr is not None
        assert attr.name == "color"
        assert attr.value == "red"
        assert attr.get_guid() in god_instance.attributes

    def test_create_attribute_returns_existing(self, god_instance):
        """Test that creating same attribute returns existing one."""
        attr1 = god_instance.create_attribute(AttributeType.SIMPLE, "color", "red")
        attr2 = god_instance.create_attribute(AttributeType.SIMPLE, "color", "red")
        
        assert attr1 is attr2
        assert attr1.get_guid() == attr2.get_guid()

    def test_create_attribute_invalid_type(self, god_instance):
        """Test creating attribute with invalid type raises error."""
        with pytest.raises(ValueError, match="Unknown attribute type"):
            god_instance.create_attribute("INVALID_TYPE", "name", "value")  # type: ignore


class TestGodCreateAspect:
    """Test create_aspect method."""

    def test_create_aspect_simple(self, god_instance, mock_page_info):
        """Test creating a simple aspect."""
        aspect = god_instance.create_aspect("=FUNC", mock_page_info)
        
        assert aspect is not None
        assert aspect.separator == "="
        assert aspect.value == "FUNC"

    def test_create_aspect_with_attributes(self, god_instance, mock_page_info):
        """Test creating aspect with attributes."""
        attr = SimpleAttribute("color", "blue")
        aspect = god_instance.create_aspect("=FUNC", mock_page_info, attributes=(attr,))
        
        assert aspect is not None
        assert attr in aspect.attributes

    def test_create_aspect_merges_attributes(self, god_instance, mock_page_info):
        """Test that creating same aspect merges attributes."""
        attr1 = SimpleAttribute("color", "blue")
        attr2 = SimpleAttribute("size", "large")
        
        aspect1 = god_instance.create_aspect("=FUNC", mock_page_info, attributes=(attr1,))
        aspect2 = god_instance.create_aspect("=FUNC", mock_page_info, attributes=(attr2,))
        
        assert aspect1 is aspect2
        assert attr1 in aspect1.attributes
        assert attr2 in aspect1.attributes

    def test_create_aspect_invalid_tag(self, god_instance, mock_page_info):
        """Test creating aspect with invalid tag returns None."""
        aspect = god_instance.create_aspect("", mock_page_info)
        
        assert aspect is None

    def test_create_aspect_composite_structure(self, god_instance, mock_page_info):
        """Test creating aspect with composite structure returns None."""
        aspect = god_instance.create_aspect("=A+B", mock_page_info)
        
        assert aspect is None


class TestGodCreateXTarget:
    """Test create_xtarget method."""

    def test_create_xtarget_with_pin_tag_returns_none(self, god_instance, mock_page_info):
        """Test that creating xtarget with pin tag returns None."""
        xtarget = god_instance.create_xtarget("=A+B:1", mock_page_info)
        
        assert xtarget is None

    def test_create_xtarget_invalid_tag_returns_none(self, god_instance, mock_page_info):
        """Test that invalid tag returns None."""
        with patch.object(god_instance, 'create_tag', return_value=None):
            xtarget = god_instance.create_xtarget("INVALID", mock_page_info)
            
            assert xtarget is None

    def test_create_xtarget_merges_attributes(self, god_instance, mock_page_info):
        """Test that creating same xtarget merges attributes."""
        attr1 = SimpleAttribute("color", "blue")
        attr2 = SimpleAttribute("size", "large")
        
        xtarget1 = god_instance.create_xtarget(
            "=DEV", mock_page_info, XTargetType.DEVICE, attributes=(attr1,))
        xtarget2 = god_instance.create_xtarget(
            "=DEV", mock_page_info, XTargetType.DEVICE, attributes=(attr2,))
        
        assert xtarget1 is xtarget2
        assert attr1 in xtarget1.attributes
        assert attr2 in xtarget1.attributes

    def test_create_xtarget_updates_type_priority(self, god_instance, mock_page_info):
        """Test that creating xtarget with higher priority type updates existing."""
        # Create with DEVICE type first
        xtarget1 = god_instance.create_xtarget(
            "=DEV", mock_page_info, XTargetType.DEVICE)
        
        # Create same tag with CABLE type (higher priority)
        xtarget2 = god_instance.create_xtarget(
            "=DEV", mock_page_info, XTargetType.CABLE)
        
        assert xtarget1 is xtarget2
        assert xtarget1.target_type == XTargetType.CABLE


class TestGodCreatePin:
    """Test create_pin method."""

    def test_create_pin_single(self, god_instance):
        """Test creating a single pin."""
        conn = Connection()
        link = Link("test", conn, "src", "dst")
        
        pin = god_instance.create_pin("=A+B:1", "src", link)
        
        assert pin is not None
        assert pin.name == "1"
        assert pin.child is None

    def test_create_pin_chain(self, god_instance):
        """Test creating a chain of pins."""
        conn = Connection()
        link = Link("test", conn, "src", "dst")
        
        pin = god_instance.create_pin("=A+B:1:2:3", "src", link)
        
        assert pin is not None
        assert pin.name == "1"
        assert pin.child is not None
        assert pin.child.name == "2"
        assert pin.child.child is not None
        assert pin.child.child.name == "3"

    def test_create_pin_no_colon_returns_none(self, god_instance):
        """Test that tag without colon returns None."""
        conn = Connection()
        link = Link("test", conn, "src", "dst")
        
        pin = god_instance.create_pin("=A+B", "src", link)
        
        assert pin is None


class TestGodCreateLink:
    """Test create_link method."""

    def test_create_link_basic(self, god_instance, mock_page_info):
        """Test creating a basic link."""
        conn = Connection()
        link = god_instance.create_link(
            "WIRE1", mock_page_info, parent=conn, src_pin_name="A1", dest_pin_name="B1")
        
        assert link is not None
        assert link.name == "WIRE1"
        assert link.parent == conn

    def test_create_link_with_attributes(self, god_instance, mock_page_info):
        """Test creating link with attributes."""
        conn = Connection()
        attr = SimpleAttribute("color", "red")
        
        link = god_instance.create_link(
            "WIRE1", mock_page_info, parent=conn, 
            src_pin_name="A1", dest_pin_name="B1", attributes=(attr,))
        
        assert link is not None
        assert attr in link.attributes

    def test_create_link_returns_existing(self, god_instance, mock_page_info):
        """Test that creating same link returns existing one."""
        conn = Connection()
        
        link1 = god_instance.create_link(
            "WIRE1", mock_page_info, parent=conn, src_pin_name="A1", dest_pin_name="B1")
        link2 = god_instance.create_link(
            "WIRE1", mock_page_info, parent=conn, src_pin_name="A1", dest_pin_name="B1")
        
        assert link1 is link2


class TestGodCreateConnection:
    """Test create_connection method."""

    def test_create_connection_with_cable_tag(self, god_instance, mock_page_info):
        """Test creating connection with cable tag."""
        conn = god_instance.create_connection(
            "=CABLE1", "=SRC", "=DEST", mock_page_info)
        
        assert conn is not None
        assert conn.through is not None
        assert conn.through.target_type == XTargetType.CABLE

    def test_create_connection_without_cable(self, god_instance, mock_page_info):
        """Test creating connection without cable tag."""
        conn = god_instance.create_connection(
            None, "=SRC", "=DEST", mock_page_info)
        
        assert conn is not None
        assert conn.through is None

    def test_create_connection_invalid_src(self, god_instance, mock_page_info):
        """Test that invalid source creates connection with None src."""
        with patch.object(god_instance, 'create_xtarget', side_effect=[None, MagicMock()]):
            conn = god_instance.create_connection(
                None, "INVALID", "=DEST", mock_page_info)
            
            assert conn is not None
            assert conn.src is None


class TestGodCreateError:
    """Test create_error method."""

    def test_create_error_adds_to_mapper(self, god_instance, mock_page_info):
        """Test that create_error adds error to mapper."""
        god_instance.create_error(
            mock_page_info, "Test error", error_type=ErrorType.WARNING)
        
        # Check that the error was added to the mapper
        # Since we create the xtarget before the error, page number is page.number + 1
        errors = god_instance.get_objects_on_page(1, "test.pdf")
        
        # Should have at least one PageError
        page_errors = [obj for obj in errors if isinstance(obj, PageError)]
        assert len(page_errors) > 0


class TestGodGetMethods:
    """Test various get methods."""

    def test_get_pages_of_object_with_guid_string(self, god_instance, mock_page_info):
        """Test getting pages of object using GUID string."""
        xtarget = god_instance.create_xtarget("=DEV", mock_page_info, XTargetType.DEVICE)
        guid = xtarget.get_guid()
        
        pages = god_instance.get_pages_of_object(guid)
        
        assert len(pages) > 0

    def test_get_objects_on_page(self, god_instance, mock_page_info):
        """Test getting objects on a specific page."""
        xtarget = god_instance.create_xtarget("=DEV", mock_page_info, XTargetType.DEVICE)
        
        # Page number is page.number + 1 = 0 + 1 = 1
        # File path needs to be absolute
        import os
        file_path = os.path.abspath("test.pdf")
        objects = god_instance.get_objects_on_page(1, file_path)
        
        assert xtarget in objects


class TestGodThreadSafety:
    """Test thread safety of God operations."""

    def test_multiple_creates_thread_safe(self, god_instance, mock_page_info):
        """Test that multiple creates don't cause issues."""
        import threading
        
        results = []
        
        def create_xtarget():
            xt = god_instance.create_xtarget("=DEV", mock_page_info, XTargetType.DEVICE)
            results.append(xt)
        
        threads = [threading.Thread(target=create_xtarget) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should return the same xtarget
        assert len(set(xt.get_guid() for xt in results)) == 1


class TestGodMerge:
    """Test merging God instances."""

    def test_iadd_merges_gods(self, test_config, mock_page_info):
        """Test that += merges two God instances."""
        god1 = God(test_config)
        god2 = God(test_config)
        
        # Create different objects in each
        xt1 = god1.create_xtarget("=DEV1", mock_page_info, XTargetType.DEVICE)
        xt2 = god2.create_xtarget("=DEV2", mock_page_info, XTargetType.DEVICE)
        
        assert xt1 is not None
        assert xt2 is not None
        
        god1 += god2
        
        assert xt1.get_guid() in god1.xtargets
        assert xt2.get_guid() in god1.xtargets

    def test_iadd_incompatible_configs_raises(self, mock_page_info):
        """Test that merging Gods with different configs raises error."""
        from typing import OrderedDict
        from indu_doc.configs import AspectsConfig, LevelConfig
        
        config1 = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Functional"),
            })
        )
        config2 = AspectsConfig(
            OrderedDict({
                "+": LevelConfig(Separator="+", Aspect="Location"),
            })
        )
        
        god1 = God(config1)
        god2 = God(config2)
        
        with pytest.raises(ValueError, match="Cannot merge Gods"):
            god1 += god2


class TestGodEquality:
    """Test God equality checks."""

    def test_equal_gods(self, test_config, mock_page_info):
        """Test that two Gods with same data are equal."""
        god1 = God(test_config)
        god2 = God(test_config)
        
        # Create identical objects
        god1.create_xtarget("=DEV", mock_page_info, XTargetType.DEVICE)
        god2.create_xtarget("=DEV", mock_page_info, XTargetType.DEVICE)
        
        assert god1 == god2

    def test_different_gods_not_equal(self, test_config, mock_page_info):
        """Test that Gods with different data are not equal."""
        god1 = God(test_config)
        god2 = God(test_config)
        
        god1.create_xtarget("=DEV1", mock_page_info, XTargetType.DEVICE)
        god2.create_xtarget("=DEV2", mock_page_info, XTargetType.DEVICE)
        
        assert god1 != god2

    def test_god_not_equal_to_other_type(self, god_instance):
        """Test that God is not equal to non-God objects."""
        assert god_instance != "not a god"
        assert god_instance != 123
        assert god_instance is not None


class TestGodReset:
    """Test God reset functionality."""

    def test_reset_clears_all_data(self, god_instance, mock_page_info):
        """Test that reset clears all stored data."""
        # Create some data
        god_instance.create_xtarget("=DEV", mock_page_info, XTargetType.DEVICE)
        god_instance.create_attribute(AttributeType.SIMPLE, "test", "value")
        god_instance.create_connection(None, "=SRC", "=DST", mock_page_info)
        
        assert len(god_instance.xtargets) > 0
        assert len(god_instance.attributes) > 0
        assert len(god_instance.connections) > 0
        
        god_instance.reset()
        
        assert len(god_instance.xtargets) == 0
        assert len(god_instance.attributes) == 0
        assert len(god_instance.connections) == 0
        assert len(god_instance.links) == 0
        assert len(god_instance.pins) == 0
        assert len(god_instance.tags) == 0
        assert len(god_instance.aspects) == 0


class TestGodCreateTag:
    """Test create_tag method."""

    def test_create_tag_basic(self, god_instance, mock_page_info):
        """Test creating a basic tag."""
        tag = god_instance.create_tag("=A+B", mock_page_info)
        
        assert tag is not None
        assert tag.tag_str == "=A+B"

    def test_create_tag_returns_existing(self, god_instance, mock_page_info):
        """Test that creating same tag returns existing one."""
        tag1 = god_instance.create_tag("=A+B", mock_page_info)
        tag2 = god_instance.create_tag("=A+B", mock_page_info)
        
        assert tag1 is tag2
        assert tag1.tag_str == tag2.tag_str

    def test_create_tag_with_footer(self, god_instance):
        """Test creating tag with footer."""
        from indu_doc.footers import PageFooter
        from unittest.mock import MagicMock
        from indu_doc.plugins.eplan_pdfs.common_page_utils import PageInfo, PageType
        
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.parent.name = "test.pdf"
        
        footer = PageFooter(
            project_name="Test",
            product_name="Test",
            tags=["=BASE", "+LOC"]
        )
        
        page_info = PageInfo(
            page=mock_page,
            page_footer=footer,
            page_type=PageType.CONNECTION_LIST
        )
        
        tag = god_instance.create_tag("=BASE", page_info)
        
        assert tag is not None
