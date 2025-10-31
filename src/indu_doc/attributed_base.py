"""
Base class for objects that can have attributes attached to them.

This module provides the abstract base class for all objects in the indu_doc
system that support attribute attachments, such as tags, connections, and targets.
"""

from abc import ABC, abstractmethod
from typing import Optional

from .attributes import Attribute


class AttributedBase(ABC):
    """
    Abstract base class for objects that can have attributes.
    
    This class provides the basic functionality for managing attributes
    that can be attached to various document objects like tags, connections,
    pins, and targets.
    
    :param attributes: Initial list of attributes to attach to this object
    :type attributes: Optional[list[Attribute]]
    """
    
    def __init__(self, attributes: Optional[list[Attribute]]) -> None:
        """
        Initialize an attributed object.
        
        :param attributes: Optional list of Attribute objects to initialize with
        :type attributes: Optional[list[Attribute]]
        """
        self.attributes: set[Attribute] = set(attributes or [])

    @abstractmethod
    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this object.
        
        This method must be implemented by all subclasses to provide
        a consistent way to uniquely identify objects across the system.
        
        :raises NotImplementedError: This is an abstract method that must be implemented by subclasses
        :return: A globally unique identifier string
        :rtype: str
        """
        raise NotImplementedError("GET GUID NOT IMPLEMENTED")
