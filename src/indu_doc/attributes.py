"""
Attribute system for attaching metadata to document objects.

This module defines the attribute framework used throughout the indu_doc system.
Attributes provide a flexible way to attach metadata to various document objects
such as tags, connections, pins, and targets. Different attribute types support
different kinds of metadata including simple key-value pairs, routing tracks,
PLC addresses, and PDF location information.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
import hashlib
from typing import Any, Union
import uuid
import numpy as np

from indu_doc.common_utils import normalize_string


class Attribute(ABC):
    """
    Abstract base class for all attribute types.
    
    Attributes provide a way to attach typed metadata to document objects.
    Each attribute has a name and implements methods for database storage,
    searching, and value retrieval.
    
    :param name: The name identifier for this attribute
    :type name: str
    """
    
    def __init__(self, name: str) -> None:
        """
        Initialize an attribute with a name.
        
        :param name: The name identifier for this attribute
        :type name: str
        """
        self.name: str = name

    @abstractmethod
    def get_db_representation(self) -> dict[str, Any]:
        """
        Return a dictionary representation suitable for database storage.
        
        The returned dictionary will be stored as JSON in the database.
        
        :return: A dictionary representation suitable for database storage
        :rtype: dict[str, Any]
        """
        pass

    @classmethod
    @abstractmethod
    def from_db_representation(cls, db_dict: dict[str, Any]) -> "Attribute":
        """
        Create an Attribute instance from its database dictionary representation.
        
        This factory method reconstructs an attribute from its stored form.
        
        :param db_dict: The dictionary representation from the database
        :type db_dict: dict[str, Any]
        :return: An instance of Attribute or its subclass
        :rtype: Attribute
        """
        pass

    @abstractmethod
    def get_search_entries(self) -> dict[str, Any]:
        """
        Return a dictionary of field-value pairs for search indexing.
        
        Extract relevant text from the attribute for search purposes.
        These entries can be used to create a search index in the database.
        
        :return: A dictionary with field names as keys and their values for searching
        :rtype: dict[str, Any]
        """
        pass

    @classmethod
    @abstractmethod
    def get_value_type(cls) -> type:
        """
        Return the type of value this attribute holds.
        
        :return: The type of value (e.g., str, int, list)
        :rtype: type
        """
        pass

    @abstractmethod
    def get_value(self) -> Any:
        """
        Return the value of this attribute.
        
        The returned value will be of the type specified by get_value_type().
        
        :return: The value of this attribute
        :rtype: Any
        """
        pass

    @abstractmethod
    def __hash__(self) -> int:
        """
        Return hash value for this attribute.
        
        :return: Hash value
        :rtype: int
        """
        pass

    @abstractmethod
    def __eq__(self, other) -> bool:
        """
        Check equality with another attribute.
        
        :param other: Another object to compare with
        :return: True if equal, False otherwise
        :rtype: bool
        """
        pass

    @abstractmethod
    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this attribute.
        
        :raises NotImplementedError: This is an abstract method that must be implemented by subclasses
        :return: A globally unique identifier string
        :rtype: str
        """
        raise NotImplementedError("GET GUID NOT IMPLEMENTED")

    def __repr__(self) -> str:
        """
        Return string representation of the attribute.
        
        :return: String representation
        :rtype: str
        """
        return f"Attribute(name={self.name})"


class SimpleAttribute(Attribute):
    """
    A simple attribute with a string value.
    
    Represents a basic attribute with a name and a string value.
    It can be used for connection colors, cross-sections, or other simple metadata.
    
    :param name: The name of the attribute
    :type name: str
    :param value: The string value of the attribute
    :type value: str
    """

    def __init__(self, name: str, value: str) -> None:
        """
        Initialize a simple attribute.
        
        :param name: The name of the attribute
        :type name: str
        :param value: The string value of the attribute
        :type value: str
        """
        super().__init__(name)
        self.value: str = value

    def get_db_representation(self) -> dict[str, Any]:
        """
        Get database representation of this attribute.
        
        :return: Dictionary with name and value
        :rtype: dict[str, Any]
        """
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_db_representation(cls, db_dict: dict[str, Any]) -> "SimpleAttribute":
        """
        Create SimpleAttribute from database representation.
        
        :param db_dict: Dictionary containing name and value
        :type db_dict: dict[str, Any]
        :return: New SimpleAttribute instance
        :rtype: SimpleAttribute
        """
        return cls(name=db_dict["name"], value=db_dict["value"])

    def get_search_entries(self) -> dict[str, Any]:
        """
        Get searchable entries for this attribute.
        
        :return: Dictionary with normalized name and value
        :rtype: dict[str, Any]
        """
        return {normalize_string(self.name): normalize_string(self.value)}

    @classmethod
    def get_value_type(cls) -> type:
        """
        Get the value type for this attribute.
        
        :return: str type
        :rtype: type
        """
        return str
    
    def get_value(self) -> str:
        """
        Get the value of this attribute.
        
        :return: The string value
        :rtype: str
        """
        return self.value

    def __hash__(self) -> int:
        """
        Return hash value based on name and value.
        
        :return: Hash value
        :rtype: int
        """
        return hash((self.name, self.value))

    def __eq__(self, other) -> bool:
        """
        Check equality with another SimpleAttribute.
        
        :param other: Another object to compare with
        :return: True if both name and value are equal
        :rtype: bool
        """
        if not isinstance(other, SimpleAttribute):
            return False
        return self.name == other.name and self.value == other.value

    def __repr__(self) -> str:
        """
        Return string representation.
        
        :return: String showing name and value
        :rtype: str
        """
        return f"{self.name} : {self.value}"

    def get_guid(self) -> str:
        """
        Get globally unique identifier for this attribute.
        
        :return: UUID based on name and value
        :rtype: str
        """
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{self.value}".encode()).digest()))


class RoutingTracksAttribute(Attribute):
    """
    An attribute representing routing tracks.
    
    This attribute holds a list of routing tracks associated with an object,
    typically used for cable routing or signal paths.
    
    :param name: The name of the attribute
    :type name: str
    :param tracks: List of track names or semicolon-separated string
    :type tracks: list[str] | str
    :param sep: Separator used for splitting string tracks, defaults to ";"
    :type sep: str, optional
    """

    def __init__(self, name: str, tracks: list[str] | str, sep=";") -> None:
        """
        Initialize a routing tracks attribute.
        
        :param name: The name of the attribute
        :type name: str
        :param tracks: List of track names or semicolon-separated string
        :type tracks: list[str] | str
        :param sep: Separator used for splitting string tracks, defaults to ";"
        :type sep: str, optional
        """
        super().__init__(name)
        if isinstance(tracks, str):
            tracks = tracks.split(sep)
        self.tracks: list[str] = tracks
        self.sep = sep

    def get_db_representation(self) -> dict[str, Any]:
        """
        Get database representation of this attribute.
        
        :return: Dictionary with name and tracks list
        :rtype: dict[str, Any]
        """
        return {"name": self.name, "tracks": self.tracks}

    @classmethod
    def from_db_representation(cls, db_dict: dict[str, Any]) -> "RoutingTracksAttribute":
        """
        Create RoutingTracksAttribute from database representation.
        
        :param db_dict: Dictionary containing name and tracks
        :type db_dict: dict[str, Any]
        :return: New RoutingTracksAttribute instance
        :rtype: RoutingTracksAttribute
        """
        return cls(name=db_dict["name"], tracks=db_dict["tracks"])

    def get_search_entries(self) -> dict[str, Any]:
        """
        Get searchable entries for this attribute.
        
        :return: Dictionary with tracks list
        :rtype: dict[str, Any]
        """
        return {"tracks": self.tracks}

    @classmethod
    def get_value_type(cls) -> Any:
        """
        Get the value type for this attribute.
        
        :return: Union type of list[str] or str
        :rtype: type
        """
        return Union[list[str], str]
    
    def get_value(self) -> Union[list[str], str]:
        """
        Get the tracks list.
        
        :return: List of track names
        :rtype: Union[list[str], str]
        """
        return self.tracks

    def __hash__(self) -> int:
        """
        Return hash value based on name and tracks.
        
        :return: Hash value
        :rtype: int
        """
        return hash((self.name, tuple(self.tracks)))

    def __eq__(self, other) -> bool:
        """
        Check equality with another RoutingTracksAttribute.
        
        :param other: Another object to compare with
        :return: True if both name and tracks are equal
        :rtype: bool
        """
        if not isinstance(other, RoutingTracksAttribute):
            return False
        return self.name == other.name and self.tracks == other.tracks

    def __repr__(self) -> str:
        """
        Return string representation.
        
        :return: String showing the tracks
        :rtype: str
        """
        return f"Route: {self.tracks}"

    def get_guid(self) -> str:
        """
        Get globally unique identifier for this attribute.
        
        :return: UUID based on name and sorted tracks
        :rtype: str
        """
        tracks_str = self.sep.join(sorted(self.tracks))
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{tracks_str}".encode()).digest()))


class PLCAddressAttribute(Attribute):
    """
    An attribute representing PLC diagram '%' addresses and their parameters.
    
    This attribute holds PLC address information with associated metadata,
    typically used for connecting to programmable logic controller diagrams.
    
    :param address: The PLC address string
    :type address: str
    :param meta: Dictionary of metadata associated with this address
    :type meta: dict[str, str]
    """

    def __init__(self, address: str, meta: dict[str, str]) -> None:
        """
        Initialize a PLC address attribute.
        
        :param address: The PLC address string
        :type address: str
        :param meta: Dictionary of metadata associated with this address
        :type meta: dict[str, str]
        """
        super().__init__(address)
        self.meta = meta


    def get_db_representation(self) -> dict[str, Any]:
        """
        Get database representation of this attribute.
        
        :return: Dictionary with name and metadata
        :rtype: dict[str, Any]
        """
        return {"name": self.name, "meta": self.meta}

    @classmethod
    def from_db_representation(cls, db_dict: dict[str, Any]) -> "PLCAddressAttribute":
        """
        Create PLCAddressAttribute from database representation.
        
        :param db_dict: Dictionary containing address and metadata
        :type db_dict: dict[str, Any]
        :return: New PLCAddressAttribute instance
        :rtype: PLCAddressAttribute
        """
        return cls(address=db_dict["name"], meta=db_dict["meta"])

    def get_search_entries(self) -> dict[str, Any]:
        """
        Get searchable entries for this attribute.
        
        :return: The metadata dictionary
        :rtype: dict[str, Any]
        """
        return self.meta

    @classmethod
    def get_value_type(cls) -> type:
        """
        Get the value type for this attribute.
        
        :return: dict[str, str] type
        :rtype: type
        """
        return dict[str, str]
    
    def get_value(self) -> dict[str, str]:
        """
        Get the metadata dictionary.
        
        :return: The metadata
        :rtype: dict[str, str]
        """
        return self.meta

    def __hash__(self) -> int:
        """
        Return hash value based on name and metadata.
        
        :return: Hash value
        :rtype: int
        """
        meta_str = ';'.join(f"{k}={v}" for k, v in sorted(self.meta.items()))
        return hash((self.name, meta_str))

    def __eq__(self, other) -> bool:
        """
        Check equality with another PLCAddressAttribute.
        
        Currently assumes all PLC addresses are unique.
        
        :param other: Another object to compare with
        :return: False (temporality assume they're unique)
        :rtype: bool
        """
        if not isinstance(other, PLCAddressAttribute):
            return False
        return False # temporality assume theyre unique; self.name == other.name and self.meta == other.meta

    def __repr__(self) -> str:
        """
        Return string representation.
        
        :return: String showing the PLC address and metadata
        :rtype: str
        """
        return f"PLC conn {self.name}: {self.meta}"

    def get_guid(self) -> str:
        """
        Get globally unique identifier for this attribute.
        
        :return: UUID based on name and metadata
        :rtype: str
        """
        meta_str = ';'.join(f"{k}={v}" for k, v in sorted(self.meta.items()))
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{meta_str}".encode()).digest()))



class PDFLocationAttribute(Attribute):
    """
    An attribute representing position information inside a PDF page.
    
    This attribute holds a bounding box rectangle where information was found
    on a specific PDF page.
    
    :param name: The name of the attribute
    :type name: str
    :param meta: Tuple containing (page_number, bounding_box)
    :type meta: tuple[int, tuple[float, float, float, float]]
    """

    def __init__(self, name: str, meta: tuple[int, tuple[float, float, float, float]]) -> None:
        """
        Initialize a PDF location attribute.
        
        :param name: The name of the attribute
        :type name: str
        :param meta: Tuple of (page_number, (x0, y0, x1, y1))
        :type meta: tuple[int, tuple[float, float, float, float]]
        """
        super().__init__(name)
        # Ensure bbox is a tuple (in case it comes from JSON as a list)
        bbox = meta[1]
        if isinstance(bbox, list):
            bbox = tuple(bbox)  # type: ignore
        self.bbox: tuple[float, float, float, float] = bbox  # type: ignore
        self.page_no = meta[0]

    def get_db_representation(self) -> dict[str, Any]:
        """
        Get database representation of this attribute.
        
        :return: Dictionary with name, bbox, and page_no
        :rtype: dict[str, Any]
        """
        return {"name": self.name, "bbox": self.bbox, "page_no": self.page_no}

    @classmethod
    def from_db_representation(cls, db_dict: dict[str, Any]) -> "PDFLocationAttribute":
        """
        Create PDFLocationAttribute from database representation.
        
        :param db_dict: Dictionary containing name, bbox, and page_no
        :type db_dict: dict[str, Any]
        :return: New PDFLocationAttribute instance
        :rtype: PDFLocationAttribute
        """
        # Ensure bbox is a tuple (JSON deserializes it as a list)
        bbox = db_dict["bbox"]
        if isinstance(bbox, list):
            bbox = tuple(bbox)
        return cls(name=db_dict["name"], meta=(db_dict["page_no"], bbox))

    def get_search_entries(self) -> dict[str, Any]:
        """
        Get searchable entries for this attribute.
        
        PDF locations cannot be searched, so returns empty dict.
        
        :return: Empty dictionary
        :rtype: dict[str, Any]
        """
        return {}  # can not be searched

    @classmethod
    def get_value_type(cls) -> Any:
        """
        Get the value type for this attribute.
        
        :return: Tuple type of (int, (float, float, float, float))
        :rtype: type
        """
        return tuple[int, tuple[float, float, float, float]]
    
    def get_value(self) -> tuple[int, tuple[float, float, float, float]]:
        """
        Get the page number and bounding box.
        
        :return: Tuple of (page_number, bbox)
        :rtype: tuple[int, tuple[float, float, float, float]]
        """
        return (self.page_no, self.bbox)

    def __hash__(self) -> int:
        """
        Return hash value based on name and bbox.
        
        :return: Hash value
        :rtype: int
        """
        return hash((self.name, self.bbox))

    def __eq__(self, other) -> bool:
        """
        Check equality with another PDFLocationAttribute.
        
        Uses numpy's allclose for floating point comparison.
        
        :param other: Another object to compare with
        :return: True if name, page, and bbox are equal (within tolerance)
        :rtype: bool
        """
        if not isinstance(other, PDFLocationAttribute):
            return False
        return self.name == other.name \
            and self.page_no == other.page_no \
            and np.allclose(self.bbox, other.bbox, rtol=1e-9, atol=1e-9)

    def __repr__(self) -> str:
        """
        Return string representation.
        
        :return: String showing the page number and bounding box
        :rtype: str
        """
        return f"Pos: page {self.page_no} {self.bbox}"

    def get_guid(self) -> str:
        """
        Get globally unique identifier for this attribute.
        
        :return: UUID based on name, page number, and bbox
        :rtype: str
        """
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{self.page_no}:{self.bbox}".encode()).digest()))

# IMP: please register new attributes here




class AttributeType(Enum):
    """
    Enumeration of available attribute types.
    
    Used for serialization and deserialization of attribute objects.
    """
    SIMPLE = "SimpleAttribute"
    ROUTING_TRACKS = "RoutingTracksAttribute"
    PLC_ADDRESS = "PLCAddressAttribute"
    PDF_LOCATION = "PDFLocationAttribute"


AvailableAttributes: dict[AttributeType, type[Attribute]] = {
    AttributeType.SIMPLE: SimpleAttribute,
    AttributeType.ROUTING_TRACKS: RoutingTracksAttribute,
    AttributeType.PLC_ADDRESS: PLCAddressAttribute,
    AttributeType.PDF_LOCATION: PDFLocationAttribute,
}
"""
Mapping from AttributeType enum values to attribute class types.

Used for deserializing attributes from their stored representations.
"""

ReverseAttributes = {cls: attr_type for attr_type, cls in AvailableAttributes.items()}
"""
Reverse mapping from attribute class types to AttributeType enum values.

Used for serializing attributes to their type identifiers.
"""

def get_attribute_type(cls) -> AttributeType:
    """
    Get the AttributeType enum value for a given attribute class.
    
    :param cls: The attribute class to look up
    :type cls: type[Attribute]
    :raises ValueError: If the class is not registered in AvailableAttributes
    :return: The corresponding AttributeType enum value
    :rtype: AttributeType
    """
    type = ReverseAttributes.get(cls, None)
    if type is None:
        raise ValueError("Attribute class is not in the AvailableAttributes lookup")
    return type
