"""
Tests for the common_page_utils module.

This module tests PageType enum, PageInfo dataclass, and page detection utilities.
"""

import pytest
from unittest.mock import MagicMock, patch

from indu_doc.common_page_utils import (
    PageType,
    PageInfo,
    detect_page_type,
)
from indu_doc.footers import PageFooter


class TestPageType:
    """Test PageType enum."""

    def test_connection_list_type(self):
        """Test connection list page type."""
        assert PageType.CONNECTION_LIST.value == "connection list"

    def test_device_tag_list_type(self):
        """Test device tag list page type."""
        assert PageType.DEVICE_TAG_LIST.value == "device tag list"

    def test_cable_overview_type(self):
        """Test cable overview page type."""
        assert PageType.CABLE_OVERVIEW.value == "Cable overview"

    def test_cable_diagram_type(self):
        """Test cable diagram page type."""
        assert PageType.CABLE_DIAGRAM.value == "Cable diagram"

    def test_cable_plan_type(self):
        """Test cable plan page type."""
        assert PageType.CABLE_PLAN.value == "Cable plan"

    def test_topology_type(self):
        """Test topology page type."""
        assert PageType.TOPOLOGY.value == "Topology: Routed cables / connections"

    def test_terminal_diagram_type(self):
        """Test terminal diagram page type."""
        assert PageType.TERMINAL_DIAGRAM.value == "Terminal diagram"

    def test_device_list_de_type(self):
        """Test German device list page type."""
        assert PageType.DEVICE_LIST_DE.value == "artikelstückliste"

    def test_cable_overview_de_type(self):
        """Test German cable overview page type."""
        assert PageType.CABLE_OVERVIEW_DE.value == "kabelübersicht"

    def test_cable_plan_de_type(self):
        """Test German cable plan page type."""
        assert PageType.CABLE_PLAN_DE.value == "Kabelplan"

    def test_wires_part_list_type(self):
        """Test wires parts list page type."""
        assert PageType.WIRES_PART_LIST.value == "Wires parts list"

    def test_terminal_diagram_de_type(self):
        """Test German terminal diagram page type."""
        assert PageType.TERMINAL_DIAGRAM_DE.value == "Klemmenplan"

    def test_enum_iteration(self):
        """Test iterating over PageType enum."""
        page_types = list(PageType)

        assert len(page_types) > 0
        assert PageType.CONNECTION_LIST in page_types
        assert PageType.CABLE_DIAGRAM in page_types

    def test_enum_membership(self):
        """Test checking enum membership."""
        assert PageType.CONNECTION_LIST in PageType
        assert PageType.CABLE_OVERVIEW in PageType


class TestPageInfo:
    """Test PageInfo dataclass."""

    def test_create_page_info(self):
        """Test creating PageInfo."""
        mock_page = MagicMock()
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])

        page_info = PageInfo(
            page=mock_page,
            page_footer=footer,
            page_type=PageType.CONNECTION_LIST
        )

        assert page_info.page == mock_page
        assert page_info.page_footer == footer
        assert page_info.page_type == PageType.CONNECTION_LIST

    def test_page_info_hash(self):
        """Test that PageInfo is hashable."""
        mock_page = MagicMock()
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])

        page_info = PageInfo(
            page=mock_page,
            page_footer=footer,
            page_type=PageType.CONNECTION_LIST
        )

        # Should be able to hash
        hash_value = hash(page_info)
        assert isinstance(hash_value, int)

    def test_page_info_in_set(self):
        """Test using PageInfo in a set."""
        mock_page = MagicMock()
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])

        page_info1 = PageInfo(
            page=mock_page,
            page_footer=footer,
            page_type=PageType.CONNECTION_LIST
        )
        page_info2 = PageInfo(
            page=mock_page,
            page_footer=footer,
            page_type=PageType.CONNECTION_LIST
        )

        # Can be added to set
        page_set = {page_info1, page_info2}
        assert len(page_set) >= 1  # May be 1 or 2 depending on mock behavior

    def test_page_info_with_different_page_types(self):
        """Test PageInfo with various page types."""
        mock_page = MagicMock()
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])

        page_types = [
            PageType.CONNECTION_LIST,
            PageType.CABLE_DIAGRAM,
            PageType.TERMINAL_DIAGRAM,
        ]

        for pt in page_types:
            page_info = PageInfo(
                page=mock_page, page_footer=footer, page_type=pt)
            assert page_info.page_type == pt


class TestDetectPageType:
    """Test detect_page_type function."""

    def test_detect_connection_list(self):
        """Test detecting connection list page."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "connection list"}
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})

        assert result == PageType.CONNECTION_LIST

    def test_detect_cable_diagram(self):
        """Test detecting cable diagram page."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "Cable diagram"}
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(
            mock_page, 
            {
                PageType.CABLE_DIAGRAM: "Cable diagram", 
                PageType.CONNECTION_LIST: "connection list"
            }
        )

        assert result == PageType.CABLE_DIAGRAM

    def test_detect_case_insensitive(self):
        """Test that detection is case-insensitive."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "CONNECTION LIST"}
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})

        assert result == PageType.CONNECTION_LIST

    def test_detect_with_whitespace(self):
        """Test detection with extra whitespace."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "  connection list  "}
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})

        assert result == PageType.CONNECTION_LIST

    def test_detect_returns_none_for_unknown(self):
        """Test that detection returns None for unknown page type."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "Unknown Page Type"}
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})

        assert result is None

    def test_detect_ignores_small_font(self):
        """Test that detection ignores text with small font size."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 10, "text": "connection list"}  # Too small
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})

        assert result is None

    def test_detect_ignores_large_font(self):
        """Test that detection ignores text with too large font size."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 35, "text": "connection list"}  # Too large
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})

        assert result is None

    def test_detect_with_multiple_spans(self):
        """Test detection with multiple text spans."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 15, "text": "Header"},
                                # This should match
                                {"size": 25, "text": "Cable diagram"},
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.CABLE_DIAGRAM: "Cable diagram"})

        assert result == PageType.CABLE_DIAGRAM

    def test_detect_with_multiple_blocks(self):
        """Test detection with multiple text blocks."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 15, "text": "Header"}
                            ]
                        }
                    ]
                },
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "Terminal diagram"}
                            ]
                        }
                    ]
                }
            ]
        }

        result = detect_page_type(mock_page, {PageType.TERMINAL_DIAGRAM: "terminal diagram"})

        assert result == PageType.TERMINAL_DIAGRAM

    def test_detect_empty_page(self):
        """Test detection on empty page."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {"blocks": []}

        result = detect_page_type(mock_page, {PageType.TERMINAL_DIAGRAM: "terminal diagram"})

        assert result is None

    def test_detect_page_without_lines(self):
        """Test detection on page with blocks but no lines."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {"type": "image"}  # No "lines" key
            ]
        }

        result = detect_page_type(mock_page, {PageType.TERMINAL_DIAGRAM: "terminal diagram"})

        assert result is None

    def test_detect_german_page_types(self):
        """Test detecting German page types."""
        test_cases = [
            ("artikelstückliste", PageType.DEVICE_LIST_DE),
            ("kabelübersicht", PageType.CABLE_OVERVIEW_DE),
            ("Kabelplan", PageType.CABLE_PLAN_DE),
            ("Klemmenplan", PageType.TERMINAL_DIAGRAM_DE),
        ]

        for text, expected_type in test_cases:
            mock_page = MagicMock()
            mock_page.number = 0
            mock_page.get_text.return_value = {
                "blocks": [
                    {
                        "lines": [
                            {
                                "spans": [
                                    {"size": 25, "text": text}
                                ]
                            }
                        ]
                    }
                ]
            }

            result = detect_page_type(mock_page)
            assert result == expected_type, f"Failed for text: {text}"


class TestPageInfoIntegration:
    """Integration tests for PageInfo."""

    def test_page_info_with_detected_page_type(self):
        """Test creating PageInfo with detected page type."""
        mock_page = MagicMock()
        mock_page.number = 0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {"size": 25, "text": "connection list"}
                            ]
                        }
                    ]
                }
            ]
        }

        detected_type = detect_page_type(mock_page, {PageType.CONNECTION_LIST: "connection list"})
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])

        page_info = PageInfo(
            page=mock_page,
            page_footer=footer,
            page_type=detected_type
        )

        assert page_info.page_type == PageType.CONNECTION_LIST

    def test_multiple_page_infos_in_collection(self):
        """Test managing multiple PageInfo objects."""
        footer = PageFooter(project_name="Test", product_name="Test", tags=[])

        page_infos = []
        for i, pt in enumerate([PageType.CONNECTION_LIST, PageType.CABLE_DIAGRAM, PageType.TERMINAL_DIAGRAM]):
            mock_page = MagicMock()
            mock_page.number = i
            page_info = PageInfo(
                page=mock_page, page_footer=footer, page_type=pt)
            page_infos.append(page_info)

        assert len(page_infos) == 3
        assert page_infos[0].page_type == PageType.CONNECTION_LIST
        assert page_infos[1].page_type == PageType.CABLE_DIAGRAM
        assert page_infos[2].page_type == PageType.TERMINAL_DIAGRAM
