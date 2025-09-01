"""
Tests for the tag.py module.
"""
import pytest
import logging
from typing import OrderedDict
from tag import Tag, try_parse_tag
from configs import AspectsConfig, LevelConfig
from footers import PageFooter


class TestTryParseTag:
    """Test cases for the try_parse_tag function."""

    def test_parse_simple_tag(self, simple_config):
        """Test parsing a simple tag with one separator."""
        tag_str = "=ProductA"
        result = try_parse_tag(tag_str, simple_config)

        assert result is not None
        assert len(result) == 1
        assert result[0] == ("=", "ProductA")

    def test_parse_complex_tag(self, sample_config):
        """Test parsing a complex tag with multiple separators."""
        tag_str = "===Func==Loc=Prod"
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        assert len(result) == 3
        expected = [("===", "Func"), ("==", "Loc"), ("=", "Prod")]
        assert result == expected

    def test_parse_tag_with_plus_separator(self, sample_config):
        """Test parsing a tag with plus separator."""
        tag_str = "++A"
        result = try_parse_tag(tag_str, sample_config)

        assert result is not None
        assert len(result) == 1
        assert result[0] == ("+", "+A")

    def test_parse_empty_tag(self, sample_config):
        """Test parsing an empty tag string."""
        tag_str = ""
        result = try_parse_tag(tag_str, sample_config)

        assert result == []

    def test_parse_whitespace_tag(self, sample_config):
        """Test parsing a tag string with only whitespace."""
        tag_str = "   "
        result = try_parse_tag(tag_str, sample_config)

        assert result == []

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
        assert len(result) == 2
        # Should match the longest separator first (===)
        assert result[0] == ("===", "Function")
        assert result[1] == ("==", "Location")


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
        expected = {"===": "Func", "==": "Loc", "=": "Prod"}
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
        expected_parts = {"=": "Prod", "==": "Loc", "===": "Func"}
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
        expected_parts = {"=": "Product", "==": "Location"}
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

        # Should only use the valid tag from footer
        assert tag.tag_str == "=ValidTag==Location"


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
        assert parts == {"=": "SimpleProduct"}

        # Merge with footer
        merged_tag = Tag.get_tag_with_footer(
            original_tag, sample_footer, sample_config)
        assert merged_tag.tag_str == "===Func==Loc=SimpleProduct"

        # Verify merged tag parts
        merged_parts = merged_tag.get_tag_parts()
        expected = {"===": "Func", "==": "Loc", "=": "SimpleProduct"}
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
