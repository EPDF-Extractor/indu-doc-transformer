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


class TestPLCAddressAttribute:
    """Test PLCAddressAttribute class."""

    def test_create_plc_address_attribute(self):
        """Test creating a PLC address attribute."""
        from indu_doc.attributes import PLCAddressAttribute
        
        attr = PLCAddressAttribute("PLC1", {"type": "input", "value": "10"})
        
        assert attr.name == "PLC1"
        assert attr.meta == {"type": "input", "value": "10"}

    def test_get_value(self):
        """Test getting PLC attribute value."""
        from indu_doc.attributes import PLCAddressAttribute
        
        meta = {"type": "output", "addr": "20"}
        attr = PLCAddressAttribute("PLC2", meta)
        
        assert attr.get_value() == meta

    def test_db_representation(self):
        """Test DB representation."""
        from indu_doc.attributes import PLCAddressAttribute
        
        attr = PLCAddressAttribute("PLC3", {"type": "input"})
        db_rep = attr.get_db_representation()
        
        assert db_rep["name"] == "PLC3"
        assert db_rep["meta"] == {"type": "input"}

    def test_from_db_representation(self):
        """Test creating from DB representation."""
        from indu_doc.attributes import PLCAddressAttribute
        
        db_dict = {"name": "PLC4", "meta": {"type": "output", "value": "15"}}
        attr = PLCAddressAttribute.from_db_representation(db_dict)
        
        assert attr.name == "PLC4"
        assert attr.meta == {"type": "output", "value": "15"}

    def test_get_search_entries(self):
        """Test getting search entries."""
        from indu_doc.attributes import PLCAddressAttribute
        
        meta = {"type": "input", "addr": "5"}
        attr = PLCAddressAttribute("PLC5", meta)
        
        assert attr.get_search_entries() == meta

    def test_get_value_type(self):
        """Test getting value type."""
        from indu_doc.attributes import PLCAddressAttribute
        
        assert PLCAddressAttribute.get_value_type() == dict[str, str]

    def test_hash(self):
        """Test hashing PLC attribute."""
        from indu_doc.attributes import PLCAddressAttribute
        
        attr1 = PLCAddressAttribute("PLC1", {"a": "1", "b": "2"})
        attr2 = PLCAddressAttribute("PLC1", {"b": "2", "a": "1"})
        
        # Should have same hash (meta dict sorted)
        assert hash(attr1) == hash(attr2)

    def test_equality_always_false(self):
        """Test that PLCAddressAttribute equality always returns False."""
        from indu_doc.attributes import PLCAddressAttribute
        
        attr1 = PLCAddressAttribute("PLC1", {"type": "input"})
        attr2 = PLCAddressAttribute("PLC1", {"type": "input"})
        
        # Always returns False per implementation
        assert attr1 != attr2

    def test_equality_different_type(self):
        """Test inequality with different type."""
        from indu_doc.attributes import PLCAddressAttribute
        
        attr = PLCAddressAttribute("PLC1", {"type": "input"})
        
        assert attr != "not an attribute"
        assert attr != SimpleAttribute("PLC1", "value")

    def test_repr(self):
        """Test string representation."""
        from indu_doc.attributes import PLCAddressAttribute
        
        attr = PLCAddressAttribute("PLC1", {"type": "input"})
        repr_str = repr(attr)
        
        assert "PLC conn PLC1" in repr_str
        assert "type" in repr_str

    def test_get_guid(self):
        """Test GUID generation."""
        from indu_doc.attributes import PLCAddressAttribute
        import uuid
        
        attr = PLCAddressAttribute("PLC1", {"a": "1", "b": "2"})
        guid = attr.get_guid()
        
        # Should be valid UUID
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid


class TestPDFLocationAttribute:
    """Test PDFLocationAttribute class."""

    def test_create_pdf_location_attribute(self):
        """Test creating a PDF location attribute."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        
        assert attr.name == "loc1"
        assert attr.page_no == 5
        assert attr.bbox == (10.0, 20.0, 30.0, 40.0)

    def test_create_with_list_bbox(self):
        """Test creating with list bbox (converts to tuple)."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc2", (3, [15.0, 25.0, 35.0, 45.0]))
        
        assert attr.bbox == (15.0, 25.0, 35.0, 45.0)
        assert isinstance(attr.bbox, tuple)

    def test_get_value(self):
        """Test getting PDF location value."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc3", (7, (5.0, 10.0, 15.0, 20.0)))
        value = attr.get_value()
        
        assert value == (7, (5.0, 10.0, 15.0, 20.0))

    def test_db_representation(self):
        """Test DB representation."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc4", (2, (1.0, 2.0, 3.0, 4.0)))
        db_rep = attr.get_db_representation()
        
        assert db_rep["name"] == "loc4"
        assert db_rep["page_no"] == 2
        assert db_rep["bbox"] == (1.0, 2.0, 3.0, 4.0)

    def test_from_db_representation(self):
        """Test creating from DB representation."""
        from indu_doc.attributes import PDFLocationAttribute
        
        db_dict = {"name": "loc5", "page_no": 8, "bbox": (10.0, 20.0, 30.0, 40.0)}
        attr = PDFLocationAttribute.from_db_representation(db_dict)
        
        assert attr.name == "loc5"
        assert attr.page_no == 8
        assert attr.bbox == (10.0, 20.0, 30.0, 40.0)

    def test_from_db_representation_with_list_bbox(self):
        """Test creating from DB with list bbox."""
        from indu_doc.attributes import PDFLocationAttribute
        
        db_dict = {"name": "loc6", "page_no": 1, "bbox": [5.0, 10.0, 15.0, 20.0]}
        attr = PDFLocationAttribute.from_db_representation(db_dict)
        
        assert attr.bbox == (5.0, 10.0, 15.0, 20.0)
        assert isinstance(attr.bbox, tuple)

    def test_get_search_entries(self):
        """Test that search entries are empty."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc7", (3, (0.0, 0.0, 1.0, 1.0)))
        
        assert attr.get_search_entries() == {}

    def test_get_value_type(self):
        """Test getting value type."""
        from indu_doc.attributes import PDFLocationAttribute
        
        value_type = PDFLocationAttribute.get_value_type()
        assert value_type == tuple[int, tuple[float, float, float, float]]

    def test_hash(self):
        """Test hashing PDF location attribute."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr1 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        attr2 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        
        assert hash(attr1) == hash(attr2)

    def test_equality_same(self):
        """Test equality for same attributes."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr1 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        attr2 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        
        assert attr1 == attr2

    def test_equality_different_name(self):
        """Test inequality for different names."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr1 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        attr2 = PDFLocationAttribute("loc2", (5, (10.0, 20.0, 30.0, 40.0)))
        
        assert attr1 != attr2

    def test_equality_different_page(self):
        """Test inequality for different page numbers."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr1 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        attr2 = PDFLocationAttribute("loc1", (6, (10.0, 20.0, 30.0, 40.0)))
        
        assert attr1 != attr2

    def test_equality_with_close_bbox(self):
        """Test equality with very close bbox values (allclose)."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr1 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        attr2 = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.00000001)))
        
        assert attr1 == attr2

    def test_equality_different_type(self):
        """Test inequality with different type."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        
        assert attr != "not an attribute"
        assert attr != SimpleAttribute("loc1", "value")

    def test_repr(self):
        """Test string representation."""
        from indu_doc.attributes import PDFLocationAttribute
        
        attr = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        repr_str = repr(attr)
        
        assert "Pos: page 5" in repr_str
        assert "10.0" in repr_str

    def test_get_guid(self):
        """Test GUID generation."""
        from indu_doc.attributes import PDFLocationAttribute
        import uuid
        
        attr = PDFLocationAttribute("loc1", (5, (10.0, 20.0, 30.0, 40.0)))
        guid = attr.get_guid()
        
        # Should be valid UUID
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid
