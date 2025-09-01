from __future__ import annotations

from typing import List, Optional

from .xtarget import XTarget

from .attributed_base import AttributedBase
from .attributes import Attribute


class Pin(AttributedBase):
    def __init__(
        self,
        name: str,
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


class Link(AttributedBase):
    def __init__(
        self,
        name: str,
        src_pin: Optional[Pin] = None,
        dest_pin: Optional[Pin] = None,
        attributes: Optional[List[Attribute]] = None,
    ) -> None:
        super().__init__(attributes)
        self.name: str = name
        self.src_pin: Optional[Pin] = src_pin
        self.dest_pin: Optional[Pin] = dest_pin

    def __repr__(self) -> str:
        return f"Link(name={self.name}, src_pin={self.src_pin}, dest_pin={self.dest_pin}, attributes={self.attributes})"


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
        self.links.append(link)

    def remove_link(self, link: Link) -> None:
        self.links = [l for l in self.links if l is not link]

    def __repr__(self) -> str:
        return f"Connection(src={self.src}, dest={self.dest}, through={self.through}, links={self.links})"
