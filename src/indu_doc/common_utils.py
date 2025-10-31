"""
Common utility functions for the indu_doc package.

This module provides utility functions used throughout the indu_doc system,
including string normalization and tag parsing helpers.
"""


from typing import Optional


def normalize_string(s: str) -> str:
    """
    Normalize a string for consistent searching.
    
    Converts to lowercase, strips whitespace, and collapses multiple
    spaces into single spaces.
    
    :param s: The string to normalize
    :type s: str
    :return: The normalized string
    :rtype: str
    """
    return ' '.join(s.lower().strip().split())

def is_pin_tag(tag: str) -> bool:
    """
    Check if a tag string contains a pin designation.
    
    Every pin designation starts from ':' character.
    
    :param tag: The tag string to check
    :type tag: str
    :return: True if the tag contains a pin designation
    :rtype: bool
    """
    # every pin for error handling starts from ':'
    return tag.find(':') != -1


def split_pin_tag(tag_pin: str) -> tuple[str, Optional[str]]:
    """
    Split a tag string into base tag and pin designation.
    
    Splits on the first ':' character. The pin part includes the ':' prefix.
    
    :param tag_pin: The combined tag and pin string (e.g., "+A1-M2:1")
    :type tag_pin: str
    :return: Tuple of (base_tag, pin_designation) where pin is None if not present
    :rtype: tuple[str, Optional[str]]
    
    Example:
        >>> split_pin_tag("+A1-M2:1")
        ('+A1-M2', ':1')
        >>> split_pin_tag("+A1-M2")
        ('+A1-M2', None)
    """
    # now I assume that pin starts from ':'
    tags = tag_pin.split(':', 1)
    # every pin for error handling starts from ':'
    return tags[0], None if len(tags) == 1 else ':' + tags[1]