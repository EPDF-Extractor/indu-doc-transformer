"""
Industrial Document Transformer Package

A Python package for processing and extracting structured data from industrial PDF documents.
"""

__version__ = "0.0.1"
__author__ = "Ahmed Abdelhay, Artsiom Drankevich"

# Core classes - most commonly used
from .god import God
from .configs import AspectsConfig, LevelConfig

# Data structures
from .xtarget import XTarget, XTargetType
from .connection import Connection, Pin, Link
from .attributes import Attribute, AttributeType, SimpleAttribute, RoutingTracksAttribute
from .tag import Tag

# Page processing
from .plugins.eplan_pdfs.common_page_utils import PageType, detect_page_type

# Base classes
from .attributed_base import AttributedBase

# Searcher
from .searcher import Searcher

# CLI entry point
from .cli import main as cli_main

__all__ = [
    # Core
    "God",
    "AspectsConfig",
    "LevelConfig",
    
    # Data structures
    "XTarget",
    "XTargetType", 
    "Connection",
    "Pin",
    "Link",
    "Attribute",
    "AttributeType",
    "SimpleAttribute",
    "RoutingTracksAttribute",
    "Tag",
    
    # Page processing
    "PageType",
    "detect_page_type",
    
    # Searcher
    "Searcher",
    
    # Base classes
    "AttributedBase",
    
    # CLI
    "cli_main",
]