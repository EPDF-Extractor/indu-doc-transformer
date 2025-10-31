"""
Page footer data structures and utilities.

This module contains classes and utilities for handling page footer information
extracted from industrial PDF documents, including project names, product names,
and associated tags.
"""

from dataclasses import dataclass

import logging

logger = logging.getLogger(__name__)


@dataclass
class PageFooter:
    """Represents footer information extracted from a document page.
    
    :param project_name: Name of the project as found in the footer
    :type project_name: str
    :param product_name: Name of the product as found in the footer  
    :type product_name: str
    :param tags: List of tag strings found in the footer
    :type tags: list[str]
    """
    project_name: str
    product_name: str
    tags: list[str]  # list of the tag strings found in the footer

    def __hash__(self) -> int:
        """Return hash value based on footer content.
        
        :return: Hash value for the footer
        :rtype: int
        """
        return hash((self.project_name, self.product_name, tuple(self.tags)))

    def __eq__(self, other) -> bool:
        """Check equality with another PageFooter instance.
        
        :param other: Object to compare with
        :type other: object
        :return: True if footers are equal, False otherwise
        :rtype: bool
        """
        if not isinstance(other, PageFooter):
            return False
        return (
            self.project_name == other.project_name
            and self.product_name == other.product_name
            and self.tags == other.tags
        )


