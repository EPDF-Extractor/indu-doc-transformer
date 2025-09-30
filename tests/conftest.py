"""
Pytest configuration and fixtures for the exploration project tests.
"""
import pytest
from typing import OrderedDict
from unittest.mock import MagicMock
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.footers import PageFooter
from indu_doc.common_page_utils import PageInfo, PageType


@pytest.fixture
def sample_config():
    """Fixture providing a sample AspectsConfig for testing."""
    return AspectsConfig(
        OrderedDict(
            {
                "===": LevelConfig(Separator="===", Aspect="Functional"),
                "==": LevelConfig(Separator="==", Aspect="Location"),
                "=": LevelConfig(Separator="=", Aspect="Product"),
                "+": LevelConfig(Separator="+", Aspect="Terminal"),
            }
        )
    )


@pytest.fixture
def simple_config():
    """Fixture providing a simpler AspectsConfig for basic testing."""
    return AspectsConfig(
        OrderedDict(
            {
                "=": LevelConfig(Separator="=", Aspect="Product"),
                "+": LevelConfig(Separator="+", Aspect="Terminal"),
            }
        )
    )


@pytest.fixture
def sample_footer():
    """Fixture providing a sample PageFooter for testing."""
    return PageFooter(
        project_name="ProjectX",
        product_name="ProductY",
        tags=["=Prod", "==Loc", "===Func"],
    )


@pytest.fixture
def empty_footer():
    """Fixture providing an empty PageFooter for testing."""
    return PageFooter(
        project_name="TestProject",
        product_name="TestProduct",
        tags=[],
    )


@pytest.fixture
def mock_page_info(sample_footer):
    """Fixture providing a mock PageInfo for testing."""
    mock_page = MagicMock()
    mock_page.number = 0
    mock_page.parent.name = "test.pdf"
    return PageInfo(
        page=mock_page,
        page_footer=sample_footer,
        page_type=PageType.CONNECTION_LIST
    )


@pytest.fixture
def mock_page_info_no_footer(empty_footer):
    """Fixture providing a mock PageInfo without footer tags for testing."""
    mock_page = MagicMock()
    mock_page.number = 0
    mock_page.parent.name = "test.pdf"
    return PageInfo(
        page=mock_page,
        page_footer=empty_footer,
        page_type=PageType.CONNECTION_LIST
    )
