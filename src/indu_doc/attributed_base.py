from abc import ABC
from typing import Optional

from .attributes import Attribute


class AttributedBase(ABC):
    def __init__(self, attributes: Optional[list[Attribute]]) -> None:
        self.attributes: list[Attribute] = attributes or []
