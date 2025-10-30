"""Tests for the attributed_base module."""

import pytest
from indu_doc.attributed_base import AttributedBase
from indu_doc.attributes import SimpleAttribute


class TestAttributedBase:
    """Test the AttributedBase abstract class."""

    def test_get_guid_not_implemented(self):
        """Test that get_guid raises NotImplementedError when called on base implementation."""

        class ConcreteAttributedBase(AttributedBase):
            def get_guid(self) -> str:
                # Call the parent implementation to test it raises NotImplementedError
                return super().get_guid()

        obj = ConcreteAttributedBase(attributes=None)

        with pytest.raises(NotImplementedError, match="GET GUID NOT IMPLEMENTED"):
            obj.get_guid()

    def test_init_with_none_attributes(self):
        """Test initialization with None attributes."""

        class ConcreteAttributedBase(AttributedBase):
            def get_guid(self) -> str:
                return "test-guid"

        obj = ConcreteAttributedBase(attributes=None)
        assert obj.attributes == set()

    def test_init_with_empty_list(self):
        """Test initialization with empty list of attributes."""

        class ConcreteAttributedBase(AttributedBase):
            def get_guid(self) -> str:
                return "test-guid"

        obj = ConcreteAttributedBase(attributes=[])
        assert obj.attributes == set()

    def test_init_with_attributes(self):
        """Test initialization with a list of attributes."""

        class ConcreteAttributedBase(AttributedBase):
            def get_guid(self) -> str:
                return "test-guid"

        attr1 = SimpleAttribute("Type", "Device")
        attr2 = SimpleAttribute("Location", "Room1")

        obj = ConcreteAttributedBase(attributes=[attr1, attr2])
        assert len(obj.attributes) == 2
        assert attr1 in obj.attributes
        assert attr2 in obj.attributes

    def test_attributes_stored_as_set(self):
        """Test that attributes are stored as a set."""

        class ConcreteAttributedBase(AttributedBase):
            def get_guid(self) -> str:
                return "test-guid"

        attr1 = SimpleAttribute("Type", "Device")

        obj = ConcreteAttributedBase(attributes=[attr1])
        assert isinstance(obj.attributes, set)

    def test_duplicate_attributes_removed(self):
        """Test that duplicate attributes are removed (set behavior)."""

        class ConcreteAttributedBase(AttributedBase):
            def get_guid(self) -> str:
                return "test-guid"

        attr1 = SimpleAttribute("Type", "Device")
        attr2 = SimpleAttribute("Type", "Device")  # Same as attr1

        obj = ConcreteAttributedBase(attributes=[attr1, attr2])
        # Both attributes are equal, so only one should be in the set
        assert len(obj.attributes) == 1
