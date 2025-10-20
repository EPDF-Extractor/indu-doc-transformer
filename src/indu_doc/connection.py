from __future__ import annotations

from functools import cache
from typing import Any, List, Optional
import uuid

from .xtarget import XTarget
import hashlib

from .attributed_base import AttributedBase
from .attributes import Attribute


class Pin(AttributedBase):
    def __init__(
        self,
        name: str,  # +A1:1
        role: str,  # src/dst
        parentLink: Link,  # a pin belongs to a link
        attributes: Optional[List[Attribute]] = None,
        child: Optional[Pin] = None,
    ) -> None:
        super().__init__(attributes)
        self.name: str = name
        self.child: Optional["Pin"] = child
        self.role: str = role
        self.parentLink: Link = parentLink
        # validate role
        if role != "src" and role != "dst":
            raise ValueError("Intalid pin type")

    def __repr__(self) -> str:
        return (
            f"Pin(name={self.name}, child={self.child}, attributes={self.attributes}) of Link({self.parentLink.name})"
        )

    def __str__(self) -> str:
        return f"Pin(name={self.name}, child={self.child}, attributes={self.attributes}) of Link({self.parentLink.name})"

    def get_guid(self) -> str:
        e = [self.name]
        e += self.role
        e += self.child.get_guid() if self.child else ["CHILD:None"]
        e += self.parentLink.get_guid() if self.parentLink else ["PARENT:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"PIN:{':'.join(e)}".encode()).digest()))

    def get_recursive_name(self) -> str:
        return self.name + (f"{self.child.get_recursive_name()}" if self.child else "")

    def to_dict(self) -> dict[str, Any]:
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
    def __init__(
        self,
        name: str,
        parent: Connection,
        src_pin_name: str,
        dest_pin_name: str,
        attributes: Optional[List[Attribute]] = None,
    ) -> None:
        super().__init__(attributes)
        self.name: str = name
        self.parent: Connection = parent
        self.src_pin_name: str = src_pin_name
        self.dest_pin_name: str = dest_pin_name

        # will be set later when we parse pins
        self.src_pin: Optional[Pin] = None
        self.dest_pin: Optional[Pin] = None

    def __repr__(self) -> str:
        return f"Link(name={self.name}, src_pin={self.src_pin_name}, dest_pin={self.dest_pin_name}, attributes={self.attributes})"

    def set_src_pin(self, pin: Pin) -> None:
        self.src_pin = pin

    def set_dest_pin(self, pin: Pin) -> None:
        self.dest_pin = pin

    def get_guid(self) -> str:
        e = [self.name]
        e += "SRC:" + self.src_pin_name if self.src_pin_name else ["SRC:None"]
        e += "DEST:" + \
            self.dest_pin_name if self.dest_pin_name else ["DEST:None"]
        e += self.parent.get_guid() if self.parent else ["PARENT:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"LINK:{':'.join(e)}".encode()).digest()))

    def to_dict(self) -> dict[str, Any]:
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
    def __init__(
        self,
        src: Optional[XTarget] = None,
        dest: Optional[XTarget] = None,
        through: Optional[XTarget] = None,
        links: Optional[List[Link]] = None,
    ) -> None:
        self.src: Optional[XTarget] = src
        self.dest: Optional[XTarget] = dest
        self.through: Optional[XTarget] = through
        self.links: List[Link] = links or []

    def add_link(self, link: Link) -> None:
        if link not in self.links:
            self.links.append(link)

    def remove_link(self, link: Link) -> None:
        self.links = [l for l in self.links if l is not link]

    def __repr__(self) -> str:
        return f"Connection(src={self.src}, dest={self.dest}, through={self.through}, links={self.links})"

    def get_guid(self) -> str:
        e: list[str] = []
        e += self.src.get_guid() if self.src else ["SRC:None"]
        e += self.dest.get_guid() if self.dest else ["DEST:None"]
        e += self.through.get_guid() if self.through else ["THROUGH:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"CONN:{':'.join(e)}".encode()).digest()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "src_target": self.src.to_dict() if self.src else None,
            "dest_target": self.dest.to_dict() if self.dest else None,
            "through_target": self.through.to_dict() if self.through else None,
            "guid"  : self.get_guid(),
            "links": [link.to_dict() for link in self.links],
        }