"""
Connection, link, and pin classes for electrical connections.

This module defines the structure for representing electrical connections
between components in industrial diagrams. A connection consists of links,
which are composed of source and destination pins.
"""

from __future__ import annotations

from typing import Any, List, Optional
import uuid

from .xtarget import XTarget
import hashlib

from .attributed_base import AttributedBase
from .attributes import Attribute


class Pin(AttributedBase):
    """
    Represents a pin (connection point) on a link.
    
    A pin is a connection terminal with a name and role (source or destination).
    Pins can have child pins for multi-level connections (e.g., +A1:1:2).
    
    :param name: The pin identifier (e.g., "+A1:1")
    :type name: str
    :param role: The role of this pin, either "src" or "dst"
    :type role: str
    :param parentLink: The link this pin belongs to
    :type parentLink: Link
    :param attributes: Optional list of attributes, defaults to None
    :type attributes: Optional[List[Attribute]], optional
    :param child: Optional child pin for multi-level connections, defaults to None
    :type child: Optional[Pin], optional
    :raises ValueError: If role is not "src" or "dst"
    """
    
    def __init__(
        self,
        name: str,  # +A1:1
        role: str,  # src/dst
        parentLink: Link,  # a pin belongs to a link
        attributes: Optional[List[Attribute]] = None,
        child: Optional[Pin] = None,
    ) -> None:
        """
        Initialize a Pin.
        
        :param name: The pin identifier
        :type name: str
        :param role: The role, must be "src" or "dst"
        :type role: str
        :param parentLink: The parent link this pin belongs to
        :type parentLink: Link
        :param attributes: Optional attributes list, defaults to None
        :type attributes: Optional[List[Attribute]], optional
        :param child: Optional child pin, defaults to None
        :type child: Optional[Pin], optional
        :raises ValueError: If role is not "src" or "dst"
        """
        super().__init__(attributes)
        self.name: str = name
        self.child: Optional["Pin"] = child
        self.role: str = role
        self.parentLink: Link = parentLink
        # validate role
        if role != "src" and role != "dst":
            raise ValueError("Intalid pin type")

    def __repr__(self) -> str:
        """
        Return detailed string representation.
        
        :return: String showing pin details and parent link
        :rtype: str
        """
        return (
            f"Pin(name={self.name}, child={self.child}, attributes={self.attributes}) of Link({self.parentLink.name})"
        )

    def __str__(self) -> str:
        """
        Return string representation.
        
        :return: String showing pin details and parent link
        :rtype: str
        """
        return f"Pin(name={self.name}, child={self.child}, attributes={self.attributes}) of Link({self.parentLink.name})"

    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this pin.
        
        The GUID is based on name, role, child pin, and parent link.
        
        :return: A globally unique identifier string
        :rtype: str
        """
        e = [self.name]
        e += self.role
        e += self.child.get_guid() if self.child else ["CHILD:None"]
        e += self.parentLink.get_guid() if self.parentLink else ["PARENT:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"PIN:{':'.join(e)}".encode()).digest()))

    def get_recursive_name(self) -> str:
        """
        Get the full pin name including all child pins.
        
        :return: Concatenated name including child pins
        :rtype: str
        """
        return self.name + (f"{self.child.get_recursive_name()}" if self.child else "")

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another Pin.
        
        :param other: Another object to compare with
        :return: True if GUIDs are equal
        :rtype: bool
        """
        if not isinstance(other, Pin):
            return False
        return self.get_guid() == other.get_guid()
    
    def __hash__(self) -> int:
        """
        Return hash value based on GUID.
        
        :return: Hash value
        :rtype: int
        """
        return hash(self.get_guid())

    def to_dict(self) -> dict[str, Any]:
        """
        Convert pin to dictionary representation.
        
        :return: Dictionary with pin data
        :rtype: dict[str, Any]
        """
        attrs = {}
        for attr in (self.attributes if self.attributes else []):
            attrs.update(attr.get_search_entries())
        return {
            "name": self.get_recursive_name(),
            "role": self.role,
            "attributes": attrs,
            "guid": self.get_guid(),
        }
        
class Link(AttributedBase):
    """
    Represents a link between two pins in a connection.
    
    A link is a named connection between a source pin and a destination pin,
    typically representing a wire or cable segment.
    
    :param name: The link identifier (often a wire/cable number)
    :type name: str
    :param parent: The parent connection this link belongs to
    :type parent: Connection
    :param src_pin_name: The source pin identifier
    :type src_pin_name: str
    :param dest_pin_name: The destination pin identifier
    :type dest_pin_name: str
    :param attributes: Optional list of attributes, defaults to None
    :type attributes: Optional[List[Attribute]], optional
    """
    
    def __init__(
        self,
        name: str,
        parent: Connection,
        src_pin_name: str,
        dest_pin_name: str,
        attributes: Optional[List[Attribute]] = None,
    ) -> None:
        """
        Initialize a Link.
        
        :param name: The link identifier
        :type name: str
        :param parent: The parent connection
        :type parent: Connection
        :param src_pin_name: Source pin identifier
        :type src_pin_name: str
        :param dest_pin_name: Destination pin identifier
        :type dest_pin_name: str
        :param attributes: Optional attributes, defaults to None
        :type attributes: Optional[List[Attribute]], optional
        """
        super().__init__(attributes)
        self.name: str = name
        self.parent: Connection = parent
        self.src_pin_name: str = src_pin_name
        self.dest_pin_name: str = dest_pin_name

        # will be set later when we parse pins
        self.src_pin: Optional[Pin] = None
        self.dest_pin: Optional[Pin] = None

    def __repr__(self) -> str:
        """
        Return detailed string representation.
        
        :return: String showing link details
        :rtype: str
        """
        return f"Link(name={self.name}, src_pin={self.src_pin_name}, dest_pin={self.dest_pin_name}, attributes={self.attributes})"

    def set_src_pin(self, pin: Pin) -> None:
        """
        Set the source pin for this link.
        
        :param pin: The source pin
        :type pin: Pin
        """
        self.src_pin = pin

    def set_dest_pin(self, pin: Pin) -> None:
        """
        Set the destination pin for this link.
        
        :param pin: The destination pin
        :type pin: Pin
        """
        self.dest_pin = pin

    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this link.
        
        The GUID is based on name, source pin, destination pin, and parent connection.
        
        :return: A globally unique identifier string
        :rtype: str
        """
        e = [self.name]
        e += "SRC:" + self.src_pin_name if self.src_pin_name else ["SRC:None"]
        e += "DEST:" + \
            self.dest_pin_name if self.dest_pin_name else ["DEST:None"]
        e += self.parent.get_guid() if self.parent else ["PARENT:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"LINK:{':'.join(e)}".encode()).digest()))

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another Link.
        
        :param other: Another object to compare with
        :return: True if GUIDs are equal
        :rtype: bool
        """
        if not isinstance(other, Link):
         
            return False
        return self.get_guid() == other.get_guid()
    
    def __hash__(self) -> int:
        """
        Return hash value based on GUID.
        
        :return: Hash value
        :rtype: int
        """
        return hash(self.get_guid())

    def to_dict(self) -> dict[str, Any]:
        """
        Convert link to dictionary representation.
        
        :return: Dictionary with link data including pins
        :rtype: dict[str, Any]
        """
        attrs = {}
        for attr in (self.attributes if self.attributes else []):
            attrs.update(attr.get_search_entries())
        return {
            "name": self.name,
            "src_pin": self.src_pin.to_dict() if self.src_pin else {"name": self.src_pin_name, "role": "src", "attributes": []},
            "dest_pin": self.dest_pin.to_dict() if self.dest_pin else {"name": self.dest_pin_name, "role": "dest", "attributes": []},
            "attributes": attrs,
            "guid": self.get_guid(),
        }

class Connection:
    """
    Represents an electrical connection between targets.
    
    A connection represents the complete path between source and destination
    targets, potentially passing through intermediate targets. It consists
    of one or more links.
    
    :param src: The source target, defaults to None
    :type src: Optional[XTarget], optional
    :param dest: The destination target, defaults to None
    :type dest: Optional[XTarget], optional
    :param through: An intermediate "through" target, defaults to None
    :type through: Optional[XTarget], optional
    :param links: List of links in this connection, defaults to None
    :type links: Optional[List[Link]], optional
    """
    
    def __init__(
        self,
        src: Optional[XTarget] = None,
        dest: Optional[XTarget] = None,
        through: Optional[XTarget] = None,
        links: Optional[List[Link]] = None,
    ) -> None:
        """
        Initialize a Connection.
        
        :param src: Source target, defaults to None
        :type src: Optional[XTarget], optional
        :param dest: Destination target, defaults to None
        :type dest: Optional[XTarget], optional
        :param through: Through target, defaults to None
        :type through: Optional[XTarget], optional
        :param links: List of links, defaults to None
        :type links: Optional[List[Link]], optional
        """
        self.src: Optional[XTarget] = src
        self.dest: Optional[XTarget] = dest
        self.through: Optional[XTarget] = through
        self.links: List[Link] = links or []

    def add_link(self, link: Link) -> None:
        """
        Add a link to this connection.
        
        :param link: The link to add
        :type link: Link
        """
        if link not in self.links:
            self.links.append(link)

    def remove_link(self, link: Link) -> None:
        """
        Remove a link from this connection.
        
        :param link: The link to remove
        :type link: Link
        """
        self.links = [l for l in self.links if l is not link]

    def __repr__(self) -> str:
        """
        Return detailed string representation.
        
        :return: String showing connection details
        :rtype: str
        """
        return f"Connection(src={self.src}, dest={self.dest}, through={self.through}, links={self.links})"

    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this connection.
        
        The GUID is based on source, destination, and through targets.
        
        :return: A globally unique identifier string
        :rtype: str
        """
        e: list[str] = []
        e += self.src.get_guid() if self.src else ["SRC:None"]
        e += self.dest.get_guid() if self.dest else ["DEST:None"]
        e += self.through.get_guid() if self.through else ["THROUGH:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"CONN:{':'.join(e)}".encode()).digest()))

    def __eq__(self, other: object) -> bool:
        """
        Check equality with another Connection.
        
        Compares by GUID which is based on src, dest, and through targets.
        
        :param other: Another object to compare with
        :return: True if GUIDs are equal
        :rtype: bool
        """
        if not isinstance(other, Connection):
            return False
        # Compare by GUID which is based on src, dest, and through
        return self.get_guid() == other.get_guid()
    
    def __hash__(self) -> int:
        """
        Return hash value based on GUID.
        
        :return: Hash value
        :rtype: int
        """
        return hash(self.get_guid())

    def to_dict(self) -> dict[str, Any]:
        """
        Convert connection to dictionary representation.
        
        :return: Dictionary with connection data including all links
        :rtype: dict[str, Any]
        """
        return {
            "src_target": self.src.to_dict() if self.src else None,
            "dest_target": self.dest.to_dict() if self.dest else None,
            "through_target": self.through.to_dict() if self.through else None,
            "guid"  : self.get_guid(),
            "links": [link.to_dict() for link in self.links],
        }