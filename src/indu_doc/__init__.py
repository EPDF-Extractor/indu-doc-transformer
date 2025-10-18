"""
Industrial Document Transformer Package

A Python package for processing and extracting structured data from industrial PDF documents.
"""

__version__ = "0.0.1"
__author__ = "Ahmed Abdelhay, Artsiom Drankevich"

# Core classes - most commonly used
from .manager import Manager
from .god import God
from .configs import AspectsConfig, LevelConfig

# Data structures
from .xtarget import XTarget, XTargetType
from .connection import Connection, Pin, Link
from .attributes import Attribute, AttributeType, SimpleAttribute, RoutingTracksAttribute
from .tag import Tag

# Page processing
from .page_processor import PageProcessor
from .table_extractor import TableExtractor
from .common_page_utils import PageType, detect_page_type
from .footers import PageFooter, PaperSize, extract_footer

# Base classes
from .attributed_base import AttributedBase

# Searcher
from .searcher import Searcher

# CLI entry point
from .cli import main as cli_main

__all__ = [
    # Core
    "Manager",
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
    "PageProcessor",
    "TableExtractor",
    "PageType",
    "detect_page_type",
    "PageFooter",
    "PaperSize",
    "extract_footer",
    
    # Searcher
    "Searcher",
    
    # Base classes
    "AttributedBase",
    
    # CLI
    "cli_main",
]