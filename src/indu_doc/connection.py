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
        attributes: Optional[List[Attribute]] = None,
        child: Optional[Pin] = None,
    ) -> None:
        super().__init__(attributes)
        self.name: str = name
        self.child: Optional["Pin"] = child

    def __repr__(self) -> str:
        return (
            f"Pin(name={self.name}, child={self.child}, attributes={self.attributes})"
        )

    def __str__(self) -> str:
        return self.get_id()

    @cache
    def get_guid(self) -> str:
        raise NotImplementedError("GET GUID CALLED ON PIN, USE GET_ID INSTEAD")

    @cache
    def get_id(self) -> str:
        e = [self.name]
        e += self.child.get_id() if self.child else ["CHILD:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"PIN:{":".join(e)}".encode()).digest()))


class Link(AttributedBase):
    def __init__(
        self,
        name: str,
        parent: Connection | None = None,
        src_pin: Optional[Pin] = None,  # guid = SRC:LINKGUID
        dest_pin: Optional[Pin] = None,  # guid = DEST:LINKGUID
        attributes: Optional[List[Attribute]] = None,
    ) -> None:
        super().__init__(attributes)
        self.name: str = name
        self.parent: Connection = parent  # type: ignore
        self.src_pin: Optional[Pin] = src_pin
        self.dest_pin: Optional[Pin] = dest_pin

    def __repr__(self) -> str:
        return f"Link(name={self.name}, src_pin={self.src_pin}, dest_pin={self.dest_pin}, attributes={self.attributes})"

    @cache
    def get_guid(self) -> str:
        e = [self.name]
        e += "SRC:" + self.src_pin.name if self.src_pin else ["SRC:None"]
        e += "DEST:" + self.dest_pin.name if self.dest_pin else ["DEST:None"]
        e += self.parent.get_guid() if self.parent else ["PARENT:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"LINK:{':'.join(e)}".encode()).digest()))


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

    @cache
    def get_guid(self) -> str:
        e: list[str] = []
        e += self.src.get_guid() if self.src else ["SRC:None"]
        e += self.dest.get_guid() if self.dest else ["DEST:None"]
        e += self.through.get_guid() if self.through else ["THROUGH:None"]
        return str(uuid.UUID(bytes=hashlib.md5(f"CONN:{':'.join(e)}".encode()).digest()))
