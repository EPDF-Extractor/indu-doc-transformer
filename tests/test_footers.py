"""Tests for the footers module."""

from indu_doc.footers import PageFooter


class TestPageFooter:
    """Test the PageFooter dataclass."""

    def test_create_page_footer(self):
        """Test creating a PageFooter instance."""
        footer = PageFooter(
            project_name="Test Project",
            product_name="Test Product",
            tags=["tag1", "tag2", "tag3"]
        )
        assert footer.project_name == "Test Project"
        assert footer.product_name == "Test Product"
        assert footer.tags == ["tag1", "tag2", "tag3"]

    def test_page_footer_hash(self):
        """Test that PageFooter can be hashed."""
        footer1 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer2 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer3 = PageFooter(
            project_name="Project B",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )

        # Same footers should have same hash
        assert hash(footer1) == hash(footer2)
        # Different footers should have different hash
        assert hash(footer1) != hash(footer3)

    def test_page_footer_equality(self):
        """Test PageFooter equality."""
        footer1 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer2 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer3 = PageFooter(
            project_name="Project B",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer4 = PageFooter(
            project_name="Project A",
            product_name="Product B",
            tags=["tag1", "tag2"]
        )
        footer5 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag3"]
        )

        # Same footers should be equal
        assert footer1 == footer2
        # Different project names should not be equal
        assert footer1 != footer3
        # Different product names should not be equal
        assert footer1 != footer4
        # Different tags should not be equal
        assert footer1 != footer5

    def test_page_footer_not_equal_to_other_types(self):
        """Test that PageFooter is not equal to other types."""
        footer = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        assert footer != "not a footer"
        assert footer != 123
        assert footer is not None
        assert footer != {"project_name": "Project A"}

    def test_page_footer_in_set(self):
        """Test that PageFooter can be used in sets."""
        footer1 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer2 = PageFooter(
            project_name="Project A",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )
        footer3 = PageFooter(
            project_name="Project B",
            product_name="Product A",
            tags=["tag1", "tag2"]
        )

        footer_set = {footer1, footer2, footer3}
        # footer1 and footer2 are equal, so only 2 unique items
        assert len(footer_set) == 2
        assert footer1 in footer_set
        assert footer3 in footer_set

    def test_page_footer_empty_tags(self):
        """Test PageFooter with empty tags list."""
        footer = PageFooter(
            project_name="Project",
            product_name="Product",
            tags=[]
        )
        assert footer.tags == []
        assert hash(footer) is not None

    def test_page_footer_tags_order_matters(self):
        """Test that tag order matters for equality."""
        footer1 = PageFooter(
            project_name="Project",
            product_name="Product",
            tags=["tag1", "tag2"]
        )
        footer2 = PageFooter(
            project_name="Project",
            product_name="Product",
            tags=["tag2", "tag1"]
        )
        assert footer1 != footer2
        assert hash(footer1) != hash(footer2)
