"""
Pytest configuration and fixtures for the exploration project tests.
"""
import pytest
from typing import OrderedDict
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.footers import PageFooter


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
