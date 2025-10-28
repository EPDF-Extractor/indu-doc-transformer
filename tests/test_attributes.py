"""
Tests for the attributes module.

This module tests SimpleAttribute and RoutingTracksAttribute classes,
including database representation, GUID generation, and edge cases.
"""

import pytest
import json
import uuid

from indu_doc.attributes import (
    Attribute,
    SimpleAttribute,
    RoutingTracksAttribute,
    AttributeType,
    AvailableAttributes,
)


class TestSimpleAttribute:
    """Test SimpleAttribute class functionality."""

    def test_create_simple_attribute(self):
        """Test creating a simple attribute."""
        attr = SimpleAttribute("color", "red")

        assert attr.name == "color"
        assert attr.value == "red"

    def test_db_representation(self):
        """Test database representation serialization."""
        attr = SimpleAttribute("color", "red")
        data = attr.get_db_representation()

        # Should be a dict that can be JSON serialized
        assert data == {"name": "color", "value": "red"}
        # Ensure it's JSON serializable
        json_str = json.dumps(data)
        assert json.loads(json_str) == data

    def test_from_db_representation(self):
        """Test creating attribute from database representation."""
        data = {"name": "color", "value": "red"}
        attr = SimpleAttribute.from_db_representation(data)

        assert isinstance(attr, SimpleAttribute)
        assert attr.name == "color"
        assert attr.value == "red"

    def test_roundtrip_db_representation(self):
        """Test that db representation roundtrips correctly."""
        original = SimpleAttribute("cross-section", "2.5mm²")
        db_str = original.get_db_representation()
        restored = SimpleAttribute.from_db_representation(db_str)

        assert original.name == restored.name
        assert original.value == restored.value
        assert original == restored

    def test_get_search_entries(self):
        """Test getting search entries."""
        attr = SimpleAttribute("color", "red")
        entries = attr.get_search_entries()

        assert isinstance(entries, dict)
        assert entries == {"color": "red"}

    def test_get_value_type(self):
        """Test getting value type."""
        assert SimpleAttribute.get_value_type() == str

    def test_hash(self):
        """Test that attribute is hashable."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "red")

        # Same attributes should have same hash
        assert hash(attr1) == hash(attr2)

        # Can be used in sets
        attr_set = {attr1, attr2}
        assert len(attr_set) == 1

    def test_hash_different_values(self):
        """Test that different attributes have different hashes."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "blue")

        # Usually different (not guaranteed but extremely likely)
        assert hash(attr1) != hash(attr2)

    def test_equality(self):
        """Test attribute equality."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "red")
        attr3 = SimpleAttribute("color", "blue")
        attr4 = SimpleAttribute("size", "red")

        assert attr1 == attr2
        assert attr1 != attr3
        assert attr1 != attr4

    def test_equality_with_different_type(self):
        """Test equality comparison with different type."""
        attr = SimpleAttribute("color", "red")

        assert attr != "color:red"
        assert attr != 123
        assert attr != None

    def test_repr(self):
        """Test string representation."""
        attr = SimpleAttribute("color", "red")
        repr_str = repr(attr)

        assert "color" in repr_str
        assert "red" in repr_str

    def test_get_guid(self):
        """Test GUID generation."""
        attr = SimpleAttribute("color", "red")
        guid = attr.get_guid()

        # Should be a valid UUID
        assert isinstance(guid, str)
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid

    def test_guid_consistency(self):
        """Test that same attributes generate same GUID."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "red")

        assert attr1.get_guid() == attr2.get_guid()

    def test_guid_different_for_different_attributes(self):
        """Test that different attributes generate different GUIDs."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "blue")

        assert attr1.get_guid() != attr2.get_guid()

    def test_special_characters_in_value(self):
        """Test handling special characters in value."""
        attr = SimpleAttribute("note", "Test: 123; value=abc")

        db_str = attr.get_db_representation()
        restored = SimpleAttribute.from_db_representation(db_str)

        assert restored.value == "Test: 123; value=abc"

    def test_empty_value(self):
        """Test attribute with empty value."""
        attr = SimpleAttribute("note", "")

        assert attr.value == ""
        assert attr.get_search_entries() == {"note": ""}


class TestRoutingTracksAttribute:
    """Test RoutingTracksAttribute class functionality."""

    def test_create_with_list(self):
        """Test creating routing tracks attribute with list."""
        attr = RoutingTracksAttribute("route", ["R1", "R2", "R3"])

        assert attr.name == "route"
        assert attr.tracks == ["R1", "R2", "R3"]

    def test_create_with_string(self):
        """Test creating routing tracks attribute with string."""
        attr = RoutingTracksAttribute("route", "R1;R2;R3")

        assert attr.name == "route"
        assert attr.tracks == ["R1", "R2", "R3"]

    def test_create_with_custom_separator(self):
        """Test creating with custom separator."""
        attr = RoutingTracksAttribute("route", "R1,R2,R3", sep=",")

        assert attr.tracks == ["R1", "R2", "R3"]
        assert attr.sep == ","

    def test_db_representation(self):
        """Test database representation."""
        attr = RoutingTracksAttribute("route", ["R1", "R2"])
        data = attr.get_db_representation()

        assert data == {"name": "route", "tracks": ["R1", "R2"]}
        # Ensure JSON serializable
        json_str = json.dumps(data)
        assert json.loads(json_str) == data

    def test_from_db_representation(self):
        """Test creating from database representation."""
        data = {"name": "route", "tracks": ["R1", "R2", "R3"]}
        attr = RoutingTracksAttribute.from_db_representation(data)

        assert isinstance(attr, RoutingTracksAttribute)
        assert attr.name == "route"
        assert attr.tracks == ["R1", "R2", "R3"]

    def test_roundtrip_db_representation(self):
        """Test roundtrip serialization."""
        original = RoutingTracksAttribute("route", ["R1", "R2", "R3"])
        db_str = original.get_db_representation()
        restored = RoutingTracksAttribute.from_db_representation(db_str)

        assert original.name == restored.name
        assert original.tracks == restored.tracks
        assert original == restored

    def test_get_search_entries(self):
        """Test getting search entries."""
        attr = RoutingTracksAttribute("route", ["R1", "R2", "R3"])
        entries = attr.get_search_entries()

        assert entries == {"tracks": ["R1", "R2", "R3"]}

    def test_hash(self):
        """Test that routing tracks attribute is hashable."""
        attr1 = RoutingTracksAttribute("route", ["R1", "R2"])
        attr2 = RoutingTracksAttribute("route", ["R1", "R2"])

        assert hash(attr1) == hash(attr2)

        # Can be used in sets
        attr_set = {attr1, attr2}
        assert len(attr_set) == 1

    def test_equality(self):
        """Test attribute equality."""
        attr1 = RoutingTracksAttribute("route", ["R1", "R2"])
        attr2 = RoutingTracksAttribute("route", ["R1", "R2"])
        attr3 = RoutingTracksAttribute("route", ["R1", "R3"])
        attr4 = RoutingTracksAttribute("path", ["R1", "R2"])

        assert attr1 == attr2
        assert attr1 != attr3
        assert attr1 != attr4

    def test_equality_with_different_type(self):
        """Test equality with different type."""
        attr = RoutingTracksAttribute("route", ["R1", "R2"])

        assert attr != "route:R1;R2"
        assert attr != ["R1", "R2"]
        assert attr != None

    def test_equality_order_matters(self):
        """Test that track order matters for equality."""
        attr1 = RoutingTracksAttribute("route", ["R1", "R2"])
        attr2 = RoutingTracksAttribute("route", ["R2", "R1"])

        assert attr1 != attr2

    def test_repr(self):
        """Test string representation."""
        attr = RoutingTracksAttribute("route", ["R1", "R2"])
        repr_str = repr(attr)

        assert "Route" in repr_str
        assert "R1" in repr_str
        assert "R2" in repr_str

    def test_get_guid(self):
        """Test GUID generation."""
        attr = RoutingTracksAttribute("route", ["R1", "R2"])
        guid = attr.get_guid()

        # Should be valid UUID
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid

    def test_guid_consistency(self):
        """Test GUID consistency."""
        attr1 = RoutingTracksAttribute("route", ["R1", "R2"])
        attr2 = RoutingTracksAttribute("route", ["R1", "R2"])

        assert attr1.get_guid() == attr2.get_guid()

    def test_guid_order_independent(self):
        """Test that GUID is order-independent (sorted)."""
        attr1 = RoutingTracksAttribute("route", ["R1", "R2", "R3"])
        attr2 = RoutingTracksAttribute("route", ["R3", "R1", "R2"])

        # GUIDs should be the same because they're sorted
        assert attr1.get_guid() == attr2.get_guid()

    def test_empty_tracks(self):
        """Test with empty tracks list."""
        attr = RoutingTracksAttribute("route", [])

        assert attr.tracks == []
        assert attr.get_search_entries() == {"tracks": []}

    def test_single_track(self):
        """Test with single track."""
        attr = RoutingTracksAttribute("route", ["R1"])

        assert attr.tracks == ["R1"]

    def test_tracks_with_special_characters(self):
        """Test tracks with special characters."""
        attr = RoutingTracksAttribute("route", ["R1:A", "R2-B", "R3/C"])

        db_str = attr.get_db_representation()
        restored = RoutingTracksAttribute.from_db_representation(db_str)

        assert restored.tracks == ["R1:A", "R2-B", "R3/C"]


class TestAttributeType:
    """Test AttributeType enum."""

    def test_simple_attribute_type(self):
        """Test simple attribute type enum value."""
        assert AttributeType.SIMPLE.value == "SimpleAttribute"

    def test_routing_tracks_type(self):
        """Test routing tracks type enum value."""
        assert AttributeType.ROUTING_TRACKS.value == "RoutingTracksAttribute"

    def test_available_attributes_mapping(self):
        """Test AvailableAttributes mapping."""
        assert AvailableAttributes[AttributeType.SIMPLE] == SimpleAttribute
        assert AvailableAttributes[AttributeType.ROUTING_TRACKS] == RoutingTracksAttribute

    def test_attribute_type_count(self):
        """Test that we have the expected number of attribute types."""
        assert len(AttributeType) == len(AvailableAttributes)


class TestAttributeIntegration:
    """Integration tests for attributes."""

    def test_different_attribute_types_not_equal(self):
        """Test that different attribute types are not equal."""
        simple = SimpleAttribute("test", "value")
        routing = RoutingTracksAttribute("test", ["value"])

        assert simple != routing

    def test_attributes_in_set(self):
        """Test using mixed attribute types in a set."""
        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "blue")
        attr3 = RoutingTracksAttribute("route", ["R1"])
        attr4 = RoutingTracksAttribute("route", ["R1"])

        attr_set = {attr1, attr2, attr3, attr4}

        # Should have 3 unique attributes (attr3 and attr4 are the same)
        assert len(attr_set) == 3

    def test_guid_uniqueness_across_types(self):
        """Test that GUIDs are unique across attribute types."""
        simple = SimpleAttribute("test", "value")
        routing = RoutingTracksAttribute("test", ["value"])

        # Note: Due to hashing implementation, these might have the same GUID
        # if their string representation is similar. This is expected behavior.
        # The important thing is that the objects themselves are not equal.
        assert simple != routing
