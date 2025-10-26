"""
Unit tests for duplicate object prevention in the God factory class.

This module tests that the God factory class properly prevents creation of
duplicate objects like XTargets, Connections, Links, Tags, Pins, and Attributes.
"""

import pytest
from typing import OrderedDict

from indu_doc.god import God
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.attributes import AttributeType, SimpleAttribute, RoutingTracksAttribute
from indu_doc.xtarget import XTargetType
from indu_doc.footers import PageFooter
from indu_doc.connection import Connection, Link


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


@pytest.fixture
def sample_footer():
    """Fixture providing a sample PageFooter for testing."""
    return PageFooter(
        project_name="TestProject",
        product_name="TestProduct",
        tags=["=FUNC", "+LOC", "-PROD"],
    )


class TestNoDuplicateXTargets:
    """Test that God doesn't create duplicate XTargets."""

    def test_same_tag_different_types_merges(self, god_instance: God, mock_page_info_no_footer):
        """Test that same tag with different types merges to higher priority type."""
        # Create with lower priority type first
        xtarget1 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.OTHER)
        assert xtarget1.target_type == XTargetType.OTHER

        # Create with higher priority type
        xtarget2 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)

        # Should be same object with upgraded type
        assert xtarget1 is xtarget2
        assert xtarget2.target_type == XTargetType.DEVICE
        assert len(god_instance.xtargets) == 1

    def test_same_tag_attributes_merged(self, god_instance: God, mock_page_info_no_footer):
        """Test that same tag with different attributes merges attributes."""
        attr1 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        attr2 = god_instance.create_attribute(
            AttributeType.SIMPLE, "size", "large")

        # Create XTarget with first attribute
        xtarget1 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr1,))
        assert len(xtarget1.attributes) == 1
        assert attr1 in xtarget1.attributes

        # Create same XTarget with second attribute
        xtarget2 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr2,))

        # Should be same object with merged attributes
        assert xtarget1 is xtarget2
        assert len(xtarget2.attributes) == 2
        assert attr1 in xtarget2.attributes
        assert attr2 in xtarget2.attributes
        assert len(god_instance.xtargets) == 1

    def test_same_tag_duplicate_attributes_not_duplicated(self, god_instance: God, mock_page_info_no_footer):
        """Test that adding same attribute twice doesn't create duplicates."""
        attr = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")

        # Create XTarget with attribute
        xtarget1 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr,))
        assert len(xtarget1.attributes) == 1

        # Try to add same attribute again
        xtarget2 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr,))

        # Should be same object with no duplicate attributes
        assert xtarget1 is xtarget2
        assert len(xtarget2.attributes) == 1
        assert attr in xtarget2.attributes
        assert len(god_instance.xtargets) == 1

    def test_multiple_calls_same_parameters(self, god_instance: God, mock_page_info_no_footer):
        """Test multiple calls with identical parameters."""
        # Create same XTarget multiple times
        xtargets = []
        for i in range(5):
            xtarget = god_instance.create_xtarget(
                "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)
            xtargets.append(xtarget)

        # All should be the same object
        for xtarget in xtargets:
            assert xtarget is xtargets[0]

        assert len(god_instance.xtargets) == 1


class TestNoDuplicateConnections:
    """Test that God doesn't create duplicate Connections."""

    def test_same_connection_parameters_same_object(self, god_instance: God, mock_page_info_no_footer):
        """Test that same connection parameters return the same object."""
        conn1 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)
        conn2 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)

        # Should be the exact same object
        assert conn1 is conn2
        assert len(god_instance.connections) == 1

    def test_same_connection_with_cable_same_object(self, god_instance: God, mock_page_info_no_footer):
        """Test that same connection through cable returns same object."""
        conn1 = god_instance.create_connection(
            "=CABLE", "=DEV1", "=DEV2", mock_page_info_no_footer)
        conn2 = god_instance.create_connection(
            "=CABLE", "=DEV1", "=DEV2", mock_page_info_no_footer)

        # Should be the exact same object
        assert conn1 is conn2
        assert len(god_instance.connections) == 1
        assert conn1.through is not None
        assert conn1.through.tag.tag_str == "=CABLE"

    def test_different_cable_different_connections(self, god_instance: God, mock_page_info_no_footer):
        """Test that different cables create different connections."""
        conn1 = god_instance.create_connection(
            "=CABLE1", "=DEV1", "=DEV2", mock_page_info_no_footer)
        conn2 = god_instance.create_connection(
            "=CABLE2", "=DEV1", "=DEV2", mock_page_info_no_footer)
        conn3 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)  # No cable

        # Should be different objects
        assert conn1 is not conn2
        assert conn1 is not conn3
        assert conn2 is not conn3

        assert len(god_instance.connections) == 3

    def test_different_devices_different_connections(self, god_instance: God, mock_page_info_no_footer):
        """Test that different devices create different connections."""
        conn1 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)
        conn2 = god_instance.create_connection(
            None, "=DEV1", "=DEV3", mock_page_info_no_footer)
        conn3 = god_instance.create_connection(
            None, "=DEV2", "=DEV3", mock_page_info_no_footer)

        # Should be different objects
        assert conn1 is not conn2
        assert conn1 is not conn3
        assert conn2 is not conn3

        assert len(god_instance.connections) == 3

    def test_reverse_connection_same_devices_different_connection(self, god_instance: God, mock_page_info_no_footer):
        """Test that reversing source/dest creates different connection."""
        conn1 = god_instance.create_connection(
            None, "=DEV1", "=DEV2", mock_page_info_no_footer)
        conn2 = god_instance.create_connection(
            None, "=DEV2", "=DEV1", mock_page_info_no_footer)

        # Should be different objects (direction matters)
        assert conn1 is not conn2
        assert len(god_instance.connections) == 2

    def test_connection_with_links_no_duplicates(self, god_instance: God, mock_page_info_no_footer):
        """Test that connection with links doesn't create duplicates."""
        conn1 = god_instance.create_connection_with_link(
            "=CABLE", "=DEV1:PIN1", "=DEV2:PIN2", mock_page_info_no_footer
        )
        conn2 = god_instance.create_connection_with_link(
            "=CABLE", "=DEV1:PIN1", "=DEV2:PIN2", mock_page_info_no_footer
        )

        # Should be the same object
        assert conn1 is conn2
        assert len(god_instance.connections) == 1
        assert len(conn1.links) >= 1  # Should have the link


class TestNoDuplicateTags:
    """Test that God doesn't create duplicate Tags."""

    def test_same_tag_string_same_object(self, god_instance: God, mock_page_info_no_footer):
        """Test that same tag string returns same Tag object."""
        tag1 = god_instance.create_tag("=DEVICE", mock_page_info_no_footer)
        tag2 = god_instance.create_tag("=DEVICE", mock_page_info_no_footer)

        assert tag1 is tag2
        assert len(god_instance.tags) == 1
        assert "=DEVICE" in god_instance.tags

    def test_same_tag_with_footer_same_object(self, god_instance, mock_page_info):
        """Test that same tag with footer returns same object."""
        tag1 = god_instance.create_tag("=DEVICE", mock_page_info)
        tag2 = god_instance.create_tag("=DEVICE", mock_page_info)

        # Should be same object (caching should work)
        assert tag1 is tag2
        assert len(god_instance.tags) == 1

    def test_different_tag_strings_different_objects(self, god_instance: God, mock_page_info_no_footer):
        """Test that different tag strings create different objects."""
        tag1 = god_instance.create_tag("=DEVICE1", mock_page_info_no_footer)
        tag2 = god_instance.create_tag("=DEVICE2", mock_page_info_no_footer)
        tag3 = god_instance.create_tag("+LOCATION", mock_page_info_no_footer)

        assert tag1 is not tag2
        assert tag1 is not tag3
        assert tag2 is not tag3

        assert len(god_instance.tags) == 3

    def test_multiple_calls_same_tag(self, god_instance: God, mock_page_info_no_footer):
        """Test multiple calls with same tag string."""
        tags = []
        for i in range(10):
            tag = god_instance.create_tag("=DEVICE", mock_page_info_no_footer)
            tags.append(tag)

        # All should be the same object
        for tag in tags:
            assert tag is tags[0]

        assert len(god_instance.tags) == 1


class TestNoDuplicatePins:
    """Test that God doesn't create duplicate Pins."""

    def test_same_pin_string_same_object(self, god_instance: God):
        """Test that same pin string returns same Pin object."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin1 = god_instance.create_pin("=DEV:PIN1", "src", link)
        pin2 = god_instance.create_pin("=DEV:PIN1", "src", link)

        assert pin1 is pin2
        assert len(god_instance.pins) == 1

    def test_same_pin_chain_same_object(self, god_instance: God):
        """Test that same pin chain returns same object."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin1 = god_instance.create_pin("=DEV:PIN1:PIN2:PIN3", "src", link)
        pin2 = god_instance.create_pin("=DEV:PIN1:PIN2:PIN3", "src", link)

        assert pin1 is pin2
        # All pins in the chain (PIN1, PIN2, PIN3) are stored in god.pins
        assert len(god_instance.pins) == 3

        # Verify the chain structure is correct
        assert pin1.name == "PIN1"
        assert pin1.child.name == "PIN2"
        assert pin1.child.child.name == "PIN3"

    def test_different_pin_strings_different_objects(self, god_instance: God):
        """Test that different pin strings create different objects."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        pin1 = god_instance.create_pin("=DEV:PIN1", "src", link)
        pin2 = god_instance.create_pin("=DEV:PIN2", "src", link)
        pin3 = god_instance.create_pin("=DEV:PIN1:PIN2", "src", link)

        assert pin1 is not pin2
        assert pin1 is not pin3
        assert pin2 is not pin3

        assert len(god_instance.pins) == 3


class TestNoDuplicateLinks:
    """Test that God doesn't create duplicate Links."""

    def test_same_link_parameters_same_object(self, god_instance: God, mock_page_info_no_footer):
        """Test that same link parameters return same Link object."""
        conn = Connection()
        link1 = god_instance.create_link(
            "TEST_LINK", mock_page_info_no_footer, parent=conn, src_pin_name="A1", dest_pin_name="B1")
        link2 = god_instance.create_link(
            "TEST_LINK", mock_page_info_no_footer, parent=conn, src_pin_name="A1", dest_pin_name="B1")

        assert link1 is link2
        assert len(god_instance.links) == 1

    def test_link_attribute_merging(self, god_instance: God, mock_page_info_no_footer):
        """Test that same link merges attributes without duplicating the link."""
        attr1 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        attr2 = god_instance.create_attribute(
            AttributeType.SIMPLE, "size", "large")

        conn = Connection()
        link1 = god_instance.create_link(
            "TEST_LINK", mock_page_info_no_footer, parent=conn, src_pin_name="A1", dest_pin_name="B1", attributes=(attr1,))
        link2 = god_instance.create_link(
            "TEST_LINK", mock_page_info_no_footer, parent=conn, src_pin_name="A1", dest_pin_name="B1", attributes=(attr2,))

        # Should be same object with merged attributes
        assert link1 is link2
        assert len(link1.attributes) == 2
        assert attr1 in link1.attributes
        assert attr2 in link1.attributes
        assert len(god_instance.links) == 1


class TestNoDuplicateAttributes:
    """Test that God doesn't create duplicate Attributes."""

    def test_same_attribute_parameters_same_object(self, god_instance: God):
        """Test that same attribute parameters store same Attribute string key."""
        attr1 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        attr2 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")

        # Note: Attributes are NOT cached, they are stored separately
        # The same string key stores the latest one
        assert str(attr1) == str(attr2)
        assert len(god_instance.attributes) == 1

    def test_different_attribute_values_different_objects(self, god_instance: God):
        """Test that different attribute values create different objects."""
        attr1 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        attr2 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "blue")
        attr3 = god_instance.create_attribute(
            AttributeType.SIMPLE, "size", "red")

        assert attr1 is not attr2
        assert attr1 is not attr3
        assert attr2 is not attr3

        assert len(god_instance.attributes) == 3

    def test_multiple_calls_same_parameters(self, god_instance: God):
        """Test multiple calls with same parameters."""
        attributes = []
        for i in range(5):
            attr = god_instance.create_attribute(
                AttributeType.SIMPLE, "color", "red")
            attributes.append(attr)

        # All should have the same string representation
        for attr in attributes:
            assert str(attr) == str(attributes[0])

        assert len(god_instance.attributes) == 1


class TestComplexNoDuplicatesScenarios:
    """Test complex scenarios involving multiple object types."""

    def test_complex_workflow_no_duplicates(self, god_instance: God, mock_page_info_no_footer):
        """Test complex workflow ensures no duplicates across all object types."""
        # Create the same complex structure twice
        for iteration in range(2):
            # Create attributes
            color_attr = god_instance.create_attribute(
                AttributeType.SIMPLE, "color", "red")
            size_attr = god_instance.create_attribute(
                AttributeType.SIMPLE, "size", "large")

            # Create XTargets
            device1 = god_instance.create_xtarget(
                "=DEVICE1", mock_page_info_no_footer, XTargetType.DEVICE, (color_attr,))
            device2 = god_instance.create_xtarget(
                "=DEVICE2", mock_page_info_no_footer, XTargetType.DEVICE, (size_attr,))
            cable = god_instance.create_xtarget(
                "=CABLE", mock_page_info_no_footer, XTargetType.CABLE)

            # Create connection with links
            connection = god_instance.create_connection_with_link(
                "=CABLE", "=DEVICE1:PIN1", "=DEVICE2:PIN2", mock_page_info_no_footer, (
                    color_attr,)
            )

        # After two iterations, counts should be the same as after one
        assert len(god_instance.attributes) == 2  # color and size
        assert len(god_instance.xtargets) == 3    # device1, device2, cable
        assert len(god_instance.connections) == 1  # one connection
        assert len(god_instance.pins) == 2        # PIN1 and PIN2
        assert len(god_instance.tags) == 3        # DEVICE1, DEVICE2, CABLE
        assert len(god_instance.links) == 1       # one link

    def test_stress_test_no_duplicates(self, god_instance: God, mock_page_info_no_footer):
        """Stress test with many repeated operations."""
        conn = Connection()
        link = Link("dummy", conn, "src", "dest")
        # Repeat the same operations many times
        for i in range(100):
            god_instance.create_attribute(AttributeType.SIMPLE, "color", "red")
            god_instance.create_tag("=DEVICE", mock_page_info_no_footer)
            god_instance.create_xtarget(
                "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE)
            god_instance.create_pin("=DEVICE:PIN1", "src", link)
            god_instance.create_link(
                "TEST_LINK", mock_page_info_no_footer, parent=conn, src_pin_name="A1", dest_pin_name="B1")
            god_instance.create_connection(
                None, "=DEV1", "=DEV2", mock_page_info_no_footer)

        # Should still have only one of each
        assert len(god_instance.attributes) == 1
        assert len(god_instance.tags) == 3  # DEVICE, DEV1, DEV2
        assert len(god_instance.xtargets) == 3  # DEVICE, DEV1, DEV2
        assert len(god_instance.pins) == 1
        assert len(god_instance.links) == 1
        assert len(god_instance.connections) == 1

    def test_interleaved_operations_no_duplicates(self, god_instance: God, mock_page_info_no_footer):
        """Test interleaved operations don't create duplicates."""
        # First round
        attr1 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        xtarget1 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr1,))

        # Second round with same parameters - note attributes are NOT cached
        attr2 = god_instance.create_attribute(
            AttributeType.SIMPLE, "color", "red")
        xtarget2 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr2,))

        # Third round with additional attribute
        attr3 = god_instance.create_attribute(
            AttributeType.SIMPLE, "size", "large")
        xtarget3 = god_instance.create_xtarget(
            "=DEVICE", mock_page_info_no_footer, XTargetType.DEVICE, (attr3,))

        # Verify no duplicates in xtargets
        assert xtarget1 is xtarget2
        assert xtarget1 is xtarget3

        # XTarget should have both attributes
        assert len(xtarget1.attributes) == 2
        assert attr1 in xtarget1.attributes
        assert attr3 in xtarget1.attributes

        assert len(god_instance.attributes) == 2
        assert len(god_instance.xtargets) == 1
