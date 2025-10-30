"""
Tests for the tag.py module.
"""
import pytest
import logging
from typing import OrderedDict
from indu_doc.tag import Tag, try_parse_tag
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.footers import PageFooter


class TestTryParseTag:
    """Test cases for the try_parse_tag function."""

    def test_parse_simple_tag(self, simple_config):
        """Test parsing a simple tag with one separator."""
        tag_str = "=ProductA"
        result = try_parse_tag(tag_str, simple_config)

        assert result is not None
        assert result == {"=": ("ProductA",)}

    def test_parse_complex_tag(self, sample_config):
        """Test parsing a complex tag with multiple separators."""
        tag_str = "===Func==Loc=Prod"
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        assert result == {"===": ("Func",), "==": ("Loc",), "=": ("Prod",)}

    def test_parse_tag_with_plus_separator(self, sample_config):
        """Test parsing a tag with plus separator."""
        tag_str = "++A"
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        assert result == {"+": ("", "A")}

    def test_parse_empty_tag(self, sample_config):
        """Test parsing an empty tag string."""
        tag_str = ""
        result = try_parse_tag(tag_str, sample_config)

        assert result == {}

    def test_parse_whitespace_tag(self, sample_config):
        """Test parsing a tag string with only whitespace."""
        tag_str = "   "
        result = try_parse_tag(tag_str, sample_config)

        assert result == {}

    def test_parse_tag_no_separators(self, sample_config):
        """Test parsing a tag string with no valid separators."""
        tag_str = "NoSeparators"
        result = try_parse_tag(tag_str, sample_config)

        assert result is None

    def test_parse_tag_overlapping_separators(self, sample_config):
        """Test parsing with overlapping separators (=== vs ==)."""
        tag_str = "===Function==Location"
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        # Should match the longest separator first (===)
        assert result == {"===": ("Function",), "==": ("Location",)}


class TestTag:
    """Test cases for the Tag class."""

    def test_tag_initialization(self, simple_config):
        """Test Tag object initialization."""
        tag_str = "=Product"
        tag = Tag(tag_str, simple_config)

        assert tag.tag_str == "=Product"
        assert tag.config == simple_config

    def test_get_tag_str_with_terminal_separator(self, simple_config):
        """Test getting tag string with terminal separator."""
        tag_str = "=Product:Terminal"
        tag = Tag(tag_str, simple_config)

        # Should remove everything after the colon
        assert tag.tag_str == "=Product"

    def test_get_tag_str_without_terminal_separator(self, simple_config):
        """Test getting tag string without terminal separator."""
        tag_str = "=Product"
        tag = Tag(tag_str, simple_config)

        assert tag.tag_str == "=Product"

    def test_get_tag_parts(self, sample_config):
        """Test getting tag parts as dictionary."""
        tag_str = "===Func==Loc=Prod"
        tag = Tag(tag_str, sample_config)

        parts = tag.get_tag_parts()
        expected = {"===": ("Func",), "==": ("Loc",), "=": ("Prod",)}
        assert parts == expected

    def test_get_tag_parts_invalid_tag(self, sample_config):
        """Test getting tag parts for invalid tag."""
        tag_str = "InvalidTag"
        tag = Tag(tag_str, sample_config)

        parts = tag.get_tag_parts()
        assert parts == {}

    def test_tag_equality(self, simple_config):
        """Test Tag equality comparison."""
        tag1 = Tag("=Product", simple_config)
        tag2 = Tag("=Product", simple_config)
        tag3 = Tag("=Different", simple_config)

        assert tag1 == tag2
        assert tag1 != tag3
        assert tag1 != "not a tag"

    def test_tag_ordering(self, simple_config):
        """Test Tag ordering comparison."""
        tag1 = Tag("=A", simple_config)
        tag2 = Tag("=B", simple_config)

        assert tag1 < tag2
        assert not tag2 < tag1

    def test_tag_hash(self, simple_config):
        """Test Tag hashing."""
        tag1 = Tag("=Product", simple_config)
        tag2 = Tag("=Product", simple_config)
        tag3 = Tag("=Different", simple_config)

        assert hash(tag1) == hash(tag2)
        assert hash(tag1) != hash(tag3)

    def test_tag_repr(self, simple_config):
        """Test Tag string representation."""
        tag = Tag("=Product", simple_config)
        expected = "Tag(tag_str='=Product'"
        assert repr(tag) == expected


class TestTagWithFooter:
    """Test cases for the get_tag_with_footer class method."""

    def test_get_tag_with_footer_complete_merge(self, sample_config, sample_footer):
        """Test merging tag with footer - complete case from original test."""
        tag = Tag.get_tag_with_footer("=Prod", sample_footer, sample_config)

        assert tag.tag_str == "===Func==Loc=Prod"
        expected_parts = {"=": ("Prod",), "==": ("Loc",), "===": ("Func",)}
        assert tag.get_tag_parts() == expected_parts

    def test_get_tag_with_footer_partial_merge(self, sample_config):
        """Test merging tag with footer - partial merge."""
        footer = PageFooter(
            project_name="TestProject",
            product_name="TestProduct",
            tags=["==Location"],
        )

        tag = Tag.get_tag_with_footer("=Product", footer, sample_config)

        assert tag.tag_str == "==Location=Product"
        expected_parts = {"===": (), "==": ("Location",), "=": ("Product",)}
        assert tag.get_tag_parts() == expected_parts

    def test_get_tag_with_footer_no_merge_needed(self, sample_config, empty_footer):
        """Test merging tag with empty footer."""
        tag = Tag.get_tag_with_footer(
            "===Full==Tag=Already", empty_footer, sample_config)

        assert tag.tag_str == "===Full==Tag=Already"

    def test_get_tag_with_footer_invalid_footer_tags(self, sample_config):
        """Test merging with footer containing invalid tags."""
        footer = PageFooter(
            project_name="TestProject",
            product_name="TestProduct",
            tags=["InvalidTag", "=ValidTag"],
        )

        tag = Tag.get_tag_with_footer("==Location", footer, sample_config)

        # No added tags since == has higher precedence than = in the footer
        assert tag.tag_str == "==Location"


class TestTagValidation:
    """Test cases for tag validation (currently not implemented)."""

    def test_is_valid_tag_not_implemented(self, simple_config):
        """Test that is_valid_tag raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            Tag.is_valid_tag("=Product", simple_config)


# Integration tests combining multiple components
class TestTagIntegration:
    """Integration tests for Tag functionality."""

    def test_complete_workflow(self, sample_config, sample_footer):
        """Test a complete workflow from parsing to footer merging."""
        # Start with a simple tag
        original_tag = "=SimpleProduct"

        # Create Tag object
        tag = Tag(original_tag, sample_config)
        assert tag.tag_str == "=SimpleProduct"

        # Get tag parts
        parts = tag.get_tag_parts()
        assert parts == {"===": (), "==": (), "=": ("SimpleProduct",)}

        # Merge with footer
        merged_tag = Tag.get_tag_with_footer(
            original_tag, sample_footer, sample_config)
        assert merged_tag.tag_str == "===Func==Loc=SimpleProduct"

        # Verify merged tag parts
        merged_parts = merged_tag.get_tag_parts()
        expected = {"===": ("Func",), "==": ("Loc",), "=": ("SimpleProduct",)}
        assert merged_parts == expected

    def test_tag_sorting(self, simple_config):
        """Test sorting multiple tags."""
        tags = [
            Tag("=Z", simple_config),
            Tag("=A", simple_config),
            Tag("=M", simple_config),
        ]

        sorted_tags = sorted(tags)
        expected_order = ["=A", "=M", "=Z"]
        actual_order = [tag.tag_str for tag in sorted_tags]

        assert actual_order == expected_order

    def test_tag_set_operations(self, simple_config):
        """Test using tags in set operations."""
        tag1 = Tag("=Product1", simple_config)
        tag2 = Tag("=Product2", simple_config)
        tag3 = Tag("=Product1", simple_config)  # Duplicate of tag1

        tag_set = {tag1, tag2, tag3}

        # Should only have 2 unique tags
        assert len(tag_set) == 2
        assert tag1 in tag_set
        assert tag2 in tag_set


class TestTagEdgeCases:
    """Test edge cases for Tag class."""

    def test_tag_lt_with_non_tag_object(self, simple_config):
        """Test less than comparison with non-Tag object."""
        tag = Tag("=Product", simple_config)
        result = tag.__lt__("not a tag")
        assert result == NotImplemented

    def test_tag_with_ampersand_in_footer(self, sample_config):
        """Test that ampersand separator is ignored in footer merging."""
        footer = PageFooter(
            project_name="TestProject",
            product_name="TestProduct",
            tags=["&Ampersand", "=ValidTag"],
        )

        tag = Tag.get_tag_with_footer("==Location", footer, sample_config)

        # Should not prepend &Ampersand since & is ignored
        assert tag.tag_str == "==Location"
        assert "&" not in tag.tag_str

    def test_tag_with_empty_value_in_footer(self, sample_config):
        """Test that empty values in footer are ignored."""
        footer = PageFooter(
            project_name="TestProject",
            product_name="TestProduct",
            tags=["=", "==ValidLoc"],  # First tag has empty value
        )

        tag = Tag.get_tag_with_footer("===Function", footer, sample_config)

        # Empty values are filtered out, so nothing should be prepended
        # since === has higher precedence than both = and ==
        assert tag.tag_str == "===Function"

    def test_try_parse_tag_multiple_sequential_separators(self, sample_config):
        """Test parsing tag with multiple sequential separators."""
        tag_str = "====Value"  # Four equals signs
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        # Should match === first, then = for the remaining =Value
        assert result == {"===": ("",), "=": ("Value",)}

    def test_try_parse_tag_separator_at_end(self, sample_config):
        """Test parsing tag with separator at the end."""
        tag_str = "=Product="
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        assert result == {"=": ("Product", "")}  # Empty value at end

    def test_tag_get_tag_parts_with_empty_values(self, sample_config):
        """Test get_tag_parts with empty values."""
        tag_str = "===Func==="
        tag = Tag(tag_str, sample_config)

        parts = tag.get_tag_parts()
        # After parsing ===Func===, we get: [("===", "Func"), ("===", "")]
        assert "===" in parts
        # Since it's a dict, only the last value for === is kept
        # Empty string from the second === at the end
        assert parts["==="] == ("Func", "")

    def test_tag_with_special_characters_in_value(self, sample_config):
        """Test tag with special characters in values."""
        tag_str = "=Product-123/ABC"
        tag = Tag(tag_str, sample_config)

        assert tag.tag_str == "=Product-123/ABC"
        parts = tag.get_tag_parts()
        assert "=" in parts

    def test_tag_ordering_with_same_prefix(self, simple_config):
        """Test tag ordering with same prefix."""
        tag1 = Tag("=Product-A", simple_config)
        tag2 = Tag("=Product-B", simple_config)
        tag3 = Tag("=ProductA", simple_config)

        assert tag1 < tag2  # "-A" < "-B"
        assert tag1 < tag3  # "-" < "A" in ASCII

    def test_tag_with_mixed_case_in_value(self, simple_config):
        """Test tag with mixed case values."""
        tag_str = "=ProductName"
        tag = Tag(tag_str, simple_config)

        assert tag.tag_str == "=ProductName"
        parts = tag.get_tag_parts()
        assert parts["="] == ("ProductName",)


class TestAspect:
    """Test cases for the Aspect class."""

    def test_aspect_creation(self):
        """Test creating an Aspect instance."""
        from indu_doc.tag import Aspect
        aspect = Aspect(separator="=", value="Product")

        assert aspect.separator == "="
        assert aspect.value == "Product"
        assert aspect.attributes == set()

    def test_aspect_with_attributes(self):
        """Test creating an Aspect with attributes."""
        from indu_doc.tag import Aspect
        from indu_doc.attributes import SimpleAttribute

        attr = SimpleAttribute("color", "red")
        aspect = Aspect(separator="=", value="Product", attributes=[attr])

        assert attr in aspect.attributes

    def test_aspect_str(self):
        """Test string representation of Aspect."""
        from indu_doc.tag import Aspect
        aspect = Aspect(separator="=", value="Product")

        assert str(aspect) == "=Product"

    def test_aspect_repr(self):
        """Test repr of Aspect."""
        from indu_doc.tag import Aspect
        aspect = Aspect(separator="=", value="Product")

        repr_str = repr(aspect)
        assert "Aspect" in repr_str
        assert "=Product" in repr_str

    def test_aspect_get_guid(self):
        """Test getting GUID of Aspect."""
        from indu_doc.tag import Aspect
        import uuid

        aspect = Aspect(separator="=", value="Product")
        guid = aspect.get_guid()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(guid)
        assert str(uuid_obj) == guid

    def test_aspect_guid_consistency(self):
        """Test that GUID is consistent for same aspects."""
        from indu_doc.tag import Aspect

        aspect1 = Aspect(separator="=", value="Product")
        aspect2 = Aspect(separator="=", value="Product")

        assert aspect1.get_guid() == aspect2.get_guid()

    def test_aspect_guid_different_for_different_aspects(self):
        """Test that GUID is different for different aspects."""
        from indu_doc.tag import Aspect

        aspect1 = Aspect(separator="=", value="Product1")
        aspect2 = Aspect(separator="=", value="Product2")

        assert aspect1.get_guid() != aspect2.get_guid()

    def test_aspect_add_attribute(self):
        """Test adding attribute to Aspect."""
        from indu_doc.tag import Aspect
        from indu_doc.attributes import SimpleAttribute

        aspect = Aspect(separator="=", value="Product")
        attr = SimpleAttribute("color", "red")

        aspect.add_attribute(attr)

        assert attr in aspect.attributes

    def test_aspect_equality_same(self):
        """Test equality of same aspects."""
        from indu_doc.tag import Aspect

        aspect1 = Aspect(separator="=", value="Product")
        aspect2 = Aspect(separator="=", value="Product")

        assert aspect1 == aspect2

    def test_aspect_equality_different_separator(self):
        """Test inequality when separator differs."""
        from indu_doc.tag import Aspect

        aspect1 = Aspect(separator="=", value="Product")
        aspect2 = Aspect(separator="==", value="Product")

        assert aspect1 != aspect2

    def test_aspect_equality_different_value(self):
        """Test inequality when value differs."""
        from indu_doc.tag import Aspect

        aspect1 = Aspect(separator="=", value="Product1")
        aspect2 = Aspect(separator="=", value="Product2")

        assert aspect1 != aspect2

    def test_aspect_equality_different_attributes(self):
        """Test inequality when attributes differ."""
        from indu_doc.tag import Aspect
        from indu_doc.attributes import SimpleAttribute

        attr1 = SimpleAttribute("color", "red")
        attr2 = SimpleAttribute("color", "blue")

        aspect1 = Aspect(separator="=", value="Product", attributes=[attr1])
        aspect2 = Aspect(separator="=", value="Product", attributes=[attr2])

        assert aspect1 != aspect2

    def test_aspect_not_equal_to_other_type(self):
        """Test that Aspect is not equal to other types."""
        from indu_doc.tag import Aspect

        aspect = Aspect(separator="=", value="Product")

        assert aspect != "=Product"
        assert aspect != 123
        assert aspect is not None

    def test_aspect_hash(self):
        """Test that Aspect can be hashed."""
        from indu_doc.tag import Aspect

        aspect = Aspect(separator="=", value="Product")
        hash_value = hash(aspect)

        assert isinstance(hash_value, int)

    def test_aspect_in_set(self):
        """Test that Aspect can be used in sets."""
        from indu_doc.tag import Aspect

        aspect1 = Aspect(separator="=", value="Product")
        aspect2 = Aspect(separator="=", value="Product")
        aspect3 = Aspect(separator="=", value="Product2")

        aspect_set = {aspect1, aspect2, aspect3}
        # aspect1 and aspect2 are equal, so only 2 unique items
        assert len(aspect_set) == 2
