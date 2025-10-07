"""
Tests for XTarget, Connection, Pin, and Link classes.

These tests cover the domain model objects for targets, connections,
pins, and links, including GUID generation and relationships.
"""

import pytest
from typing import OrderedDict
from unittest.mock import MagicMock

from indu_doc.xtarget import XTarget, XTargetType, XTargetTypePriority
from indu_doc.connection import Connection, Pin, Link
from indu_doc.tag import Tag
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.attributes import SimpleAttribute
from indu_doc.footers import PageFooter


@pytest.fixture
def test_config():
    """Fixture providing test AspectsConfig."""
    return AspectsConfig(
        OrderedDict(
            {
                "=": LevelConfig(Separator="=", Aspect="Functional"),
                "+": LevelConfig(Separator="+", Aspect="Location"),
                "-": LevelConfig(Separator="-", Aspect="Product"),
            }
        )
    )


@pytest.fixture
def sample_tag(test_config):
    """Fixture providing a sample tag."""
    footer = PageFooter(project_name="Test", product_name="Test", tags=[])
    return Tag.get_tag_with_footer("=DEV+LOC-PROD", footer, test_config)


@pytest.fixture
def sample_xtarget(sample_tag, test_config):
    """Fixture providing a sample XTarget."""
    return XTarget(sample_tag, test_config, XTargetType.DEVICE)


class TestXTargetType:
    """Test XTargetType enum."""

    def test_device_type(self):
        """Test device type enum value."""
        assert XTargetType.DEVICE.value == "device"

    def test_strip_type(self):
        """Test strip type enum value."""
        assert XTargetType.STRIP.value == "strip"

    def test_cable_type(self):
        """Test cable type enum value."""
        assert XTargetType.CABLE.value == "cable"

    def test_other_type(self):
        """Test other type enum value."""
        assert XTargetType.OTHER.value == "other"

    def test_type_priority(self):
        """Test XTargetType priority mapping."""
        assert XTargetTypePriority[XTargetType.CABLE] == 3
        assert XTargetTypePriority[XTargetType.DEVICE] == 2
        assert XTargetTypePriority[XTargetType.STRIP] == 1
        assert XTargetTypePriority[XTargetType.OTHER] == 0

    def test_priority_ordering(self):
        """Test that cable has highest priority."""
        cable_priority = XTargetTypePriority[XTargetType.CABLE]
        device_priority = XTargetTypePriority[XTargetType.DEVICE]
        strip_priority = XTargetTypePriority[XTargetType.STRIP]
        other_priority = XTargetTypePriority[XTargetType.OTHER]

        assert cable_priority > device_priority > strip_priority > other_priority


class TestXTarget:
    """Test XTarget class."""

    def test_create_xtarget(self, sample_tag, test_config):
        """Test creating an XTarget."""
        xtarget = XTarget(sample_tag, test_config, XTargetType.DEVICE)

        assert xtarget.tag == sample_tag
        assert xtarget.target_type == XTargetType.DEVICE
        assert xtarget.configs == test_config

    def test_create_with_attributes(self, sample_tag, test_config):
        """Test creating XTarget with attributes."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("size", "large")

        xtarget = XTarget(sample_tag, test_config,
                          XTargetType.DEVICE, [attr1, attr2])

        assert attr1 in xtarget.attributes
        assert attr2 in xtarget.attributes

    def test_add_attribute(self, sample_xtarget):
        """Test adding an attribute to XTarget."""
        attr = SimpleAttribute("color", "blue")
        sample_xtarget.add_attribute(attr)

        assert attr in sample_xtarget.attributes

    def test_remove_attribute(self, sample_xtarget):
        """Test removing an attribute from XTarget."""
        attr = SimpleAttribute("color", "red")
        sample_xtarget.add_attribute(attr)
        sample_xtarget.remove_attribute(attr)

        assert attr not in sample_xtarget.attributes

    def test_get_attributes_by_name(self, sample_xtarget):
        """Test getting attributes by name."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "blue")
        attr3 = SimpleAttribute("size", "large")

        sample_xtarget.add_attribute(attr1)
        sample_xtarget.add_attribute(attr2)
        sample_xtarget.add_attribute(attr3)

        color_attrs = sample_xtarget.get_attributes("color")

        assert len(color_attrs) == 2
        assert attr1 in color_attrs
        assert attr2 in color_attrs
        assert attr3 not in color_attrs

    def test_get_attributes_nonexistent(self, sample_xtarget):
        """Test getting attributes with nonexistent name."""
        attrs = sample_xtarget.get_attributes("nonexistent")

        assert attrs == []

    def test_get_name(self, test_config):
        """Test getting XTarget name."""
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])
        tag = Tag.get_tag_with_footer("=FUNC+LOC-PROD", footer, test_config)
        xtarget = XTarget(tag, test_config, XTargetType.DEVICE)

        name = xtarget.get_name()

        # Name should be reconstructed from tag parts in config order
        assert "=" in name
        assert "+" in name
        assert "-" in name

    def test_get_name_empty_tag(self, test_config):
        """Test getting name with empty tag."""
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])
        # Create a tag with no valid separators
        mock_tag = MagicMock()
        mock_tag.get_tag_parts.return_value = {}
        mock_tag.tag_str = ""

        xtarget = XTarget(mock_tag, test_config, XTargetType.OTHER)
        name = xtarget.get_name()

        assert name == ""

    def test_get_guid(self, sample_xtarget):
        """Test GUID generation."""
        guid = sample_xtarget.get_guid()

        # Should be valid UUID string
        import uuid
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid

    def test_guid_consistency(self, sample_tag, test_config):
        """Test that same tags generate same GUID."""
        xtarget1 = XTarget(sample_tag, test_config, XTargetType.DEVICE)
        xtarget2 = XTarget(sample_tag, test_config, XTargetType.DEVICE)

        assert xtarget1.get_guid() == xtarget2.get_guid()

    def test_guid_cached(self, sample_xtarget):
        """Test that GUID is cached."""
        guid1 = sample_xtarget.get_guid()
        guid2 = sample_xtarget.get_guid()

        # Should return same value
        assert guid1 == guid2

    def test_str_representation(self, sample_xtarget):
        """Test string representation."""
        str_repr = str(sample_xtarget)

        # Should return tag string
        assert str_repr == sample_xtarget.tag.tag_str

    def test_repr_representation(self, sample_xtarget):
        """Test repr representation."""
        repr_str = repr(sample_xtarget)

        assert "Object" in repr_str
        assert "tag=" in repr_str
        assert "attributes=" in repr_str

    def test_default_target_type(self, sample_tag, test_config):
        """Test default target type is OTHER."""
        xtarget = XTarget(sample_tag, test_config)

        assert xtarget.target_type == XTargetType.OTHER


class TestPin:
    """Test Pin class."""

    def test_create_pin(self):
        """Test creating a pin."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin = Pin("A1", "src", link)

        assert pin.name == "A1"
        assert pin.child is None

    def test_create_pin_with_child(self):
        """Test creating pin with child."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        child = Pin("1", "src", link)
        pin = Pin("A1", "src", link, child=child)

        assert pin.name == "A1"
        assert pin.child == child

    def test_create_pin_chain(self):
        """Test creating a pin chain."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin3 = Pin("3", "src", link)
        pin2 = Pin("2", "src", link, child=pin3)
        pin1 = Pin("1", "src", link, child=pin2)

        assert pin1.name == "1"
        assert pin1.child.name == "2"
        assert pin1.child.child.name == "3"

    def test_pin_with_attributes(self):
        """Test pin with attributes."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        attr = SimpleAttribute("color", "red")
        pin = Pin("A1", "src", link, attributes=[attr])

        assert attr in pin.attributes

    def test_repr(self):
        """Test pin repr."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin = Pin("A1", "src", link)
        repr_str = repr(pin)

        assert "Pin" in repr_str
        assert "A1" in repr_str

    def test_str(self):
        """Test pin str."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin = Pin("A1", "src", link)
        str_repr = str(pin)

        # Should return the ID
        assert isinstance(str_repr, str)

    def test_get_guid(self):
        """Test getting pin GUID."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin = Pin("A1", "src", link)
        pin_guid = pin.get_guid()

        # Should be valid UUID
        import uuid
        uuid_obj = uuid.UUID(pin_guid)
        assert str(uuid_obj) == pin_guid

    def test_get_guid_with_child(self):
        """Test getting GUID with child."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        child = Pin("1", "src", link)
        pin = Pin("A1", "src", link, child=child)

        pin_guid = pin.get_guid()

        # Should be different from pin without child
        pin_no_child_guid = Pin("A1", "src", link).get_guid()
        assert pin_guid != pin_no_child_guid

    def test_get_guid_consistency(self):
        """Test GUID consistency."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin1 = Pin("A1", "src", link, child=Pin("1", "src", link))
        pin2 = Pin("A1", "src", link, child=Pin("1", "src", link))

        assert pin1.get_guid() == pin2.get_guid()

    def test_get_guid_raises_error(self):
        """Test that get_guid returns a string."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin = Pin("A1", "src", link)

        guid = pin.get_guid()
        assert isinstance(guid, str)


class TestLink:
    """Test Link class."""

    def test_create_link(self):
        """Test creating a link."""
        conn = Connection()
        link = Link("CABLE1", conn, "src", "dest")

        assert link.name == "CABLE1"
        assert link.parent == conn
        assert link.src_pin is None
        assert link.dest_pin is None

    def test_create_link_with_pins(self):
        """Test creating link with pins."""
        conn = Connection()
        link = Link("CABLE1", conn, "A1", "B1")
        src_pin = Pin("A1", "src", link)
        dest_pin = Pin("B1", "dest", link)

        link.set_src_pin(src_pin)
        link.set_dest_pin(dest_pin)

        assert link.src_pin == src_pin
        assert link.dest_pin == dest_pin

    def test_create_link_with_parent(self, sample_xtarget):
        """Test creating link with parent connection."""
        conn = Connection(src=sample_xtarget, dest=sample_xtarget)
        link = Link("CABLE1", conn, "src", "dest")

        assert link.parent == conn

    def test_link_with_attributes(self):
        """Test link with attributes."""
        conn = Connection()
        attr = SimpleAttribute("color", "red")
        link = Link("CABLE1", conn, "src", "dest", attributes=[attr])

        assert attr in link.attributes

    def test_repr(self):
        """Test link repr."""
        conn = Connection()
        link = Link("CABLE1", conn, "src", "dest")
        repr_str = repr(link)

        assert "Link" in repr_str
        assert "CABLE1" in repr_str

    def test_get_guid(self):
        """Test getting link GUID."""
        conn = Connection()
        link = Link("CABLE1", conn, "src", "dest")
        guid = link.get_guid()

        # Should be valid UUID
        import uuid
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid

    def test_get_guid_with_pins(self):
        """Test GUID with pins."""
        conn = Connection()
        link = Link("CABLE1", conn, "A1", "B1")
        src_pin = Pin("A1", "src", link)
        dest_pin = Pin("B1", "dest", link)
        link.set_src_pin(src_pin)
        link.set_dest_pin(dest_pin)

        guid = link.get_guid()

        # Should be different from link without pins
        link_no_pins = Link("CABLE1", conn, "src", "dest")
        assert guid != link_no_pins.get_guid()

    def test_get_guid_consistency(self):
        """Test GUID consistency."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        src_pin = Pin("A1", "src", link)
        dest_pin = Pin("B1", "dest", link)

        link1 = Link("CABLE1", conn, "A1", "B1")
        link1.set_src_pin(src_pin)
        link1.set_dest_pin(dest_pin)
        link2 = Link("CABLE1", conn, "A1", "B1")
        link2.set_src_pin(Pin("A1", "src", link))
        link2.set_dest_pin(Pin("B1", "dest", link))

        # Should have same GUID (same structure)
        assert link1.get_guid() == link2.get_guid()


class TestConnection:
    """Test Connection class."""

    def test_create_connection(self, sample_xtarget):
        """Test creating a connection."""
        xtarget2 = XTarget(sample_xtarget.tag,
                           sample_xtarget.configs, XTargetType.DEVICE)
        conn = Connection(src=sample_xtarget, dest=xtarget2)

        assert conn.src == sample_xtarget
        assert conn.dest == xtarget2
        assert conn.through is None
        assert conn.links == []

    def test_create_connection_with_cable(self, sample_xtarget, test_config):
        """Test creating connection with cable (through)."""
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])
        cable_tag = Tag.get_tag_with_footer("=CABLE", footer, test_config)
        cable = XTarget(cable_tag, test_config, XTargetType.CABLE)

        conn = Connection(src=sample_xtarget,
                          dest=sample_xtarget, through=cable)

        assert conn.through == cable

    def test_add_link(self):
        """Test adding link to connection."""
        conn = Connection()
        link = Link("CABLE1", conn, "src", "dest")

        conn.add_link(link)

        assert link in conn.links

    def test_add_link_no_duplicates(self):
        """Test that adding same link twice doesn't create duplicate."""
        conn = Connection()
        link = Link("CABLE1", conn, "src", "dest")

        conn.add_link(link)
        conn.add_link(link)

        assert len(conn.links) == 1

    def test_remove_link(self):
        """Test removing link from connection."""
        conn = Connection()
        link1 = Link("CABLE1", conn, "src1", "dest1")
        link2 = Link("CABLE2", conn, "src2", "dest2")

        conn.add_link(link1)
        conn.add_link(link2)
        conn.remove_link(link1)

        assert link1 not in conn.links
        assert link2 in conn.links

    def test_repr(self, sample_xtarget):
        """Test connection repr."""
        conn = Connection(src=sample_xtarget, dest=sample_xtarget)
        repr_str = repr(conn)

        assert "Connection" in repr_str
        assert "src=" in repr_str
        assert "dest=" in repr_str

    def test_get_guid(self, sample_xtarget):
        """Test getting connection GUID."""
        xtarget2 = XTarget(sample_xtarget.tag,
                           sample_xtarget.configs, XTargetType.DEVICE)
        conn = Connection(src=sample_xtarget, dest=xtarget2)

        guid = conn.get_guid()

        # Should be valid UUID
        import uuid
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid

    def test_get_guid_with_cable(self, sample_xtarget, test_config):
        """Test GUID with cable."""
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])
        cable_tag = Tag.get_tag_with_footer("=CABLE", footer, test_config)
        cable = XTarget(cable_tag, test_config, XTargetType.CABLE)

        conn = Connection(src=sample_xtarget,
                          dest=sample_xtarget, through=cable)
        guid = conn.get_guid()

        # Should be different from virtual cable connection
        conn_virtual = Connection(src=sample_xtarget, dest=sample_xtarget)
        assert guid != conn_virtual.get_guid()

    def test_get_guid_consistency(self, sample_xtarget):
        """Test GUID consistency."""
        conn1 = Connection(src=sample_xtarget, dest=sample_xtarget)
        conn2 = Connection(src=sample_xtarget, dest=sample_xtarget)

        assert conn1.get_guid() == conn2.get_guid()

    def test_connection_with_none_values(self):
        """Test connection with None values."""
        conn = Connection(src=None, dest=None, through=None)

        assert conn.src is None
        assert conn.dest is None
        assert conn.through is None

        # Should still generate GUID
        guid = conn.get_guid()
        assert isinstance(guid, str)

    def test_create_with_links(self):
        """Test creating connection with links."""
        conn = Connection()
        link1 = Link("CABLE1", conn, "src1", "dest1")
        link2 = Link("CABLE2", conn, "src2", "dest2")

        conn = Connection(links=[link1, link2])

        assert len(conn.links) == 2
        assert link1 in conn.links
        assert link2 in conn.links


class TestAttributedBaseIntegration:
    """Test AttributedBase functionality through XTarget."""

    def test_attributes_initialized_as_set(self, sample_xtarget):
        """Test that attributes are stored as a set."""
        assert isinstance(sample_xtarget.attributes, set)

    def test_add_duplicate_attribute(self, sample_xtarget):
        """Test adding duplicate attribute."""
        attr = SimpleAttribute("color", "red")

        sample_xtarget.add_attribute(attr)
        sample_xtarget.add_attribute(attr)

        # Should only have one instance
        assert len([a for a in sample_xtarget.attributes if a == attr]) == 1

    def test_remove_nonexistent_attribute(self, sample_xtarget):
        """Test removing nonexistent attribute doesn't raise error."""
        attr = SimpleAttribute("color", "red")

        # Should not raise error
        sample_xtarget.remove_attribute(attr)
