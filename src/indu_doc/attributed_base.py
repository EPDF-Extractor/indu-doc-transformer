from abc import ABC
from typing import Optional

from .attributes import Attribute


class AttributedBase(ABC):
    def __init__(self, attributes: Optional[list[Attribute]]) -> None:
        self.attributes: set[Attribute] = set(attributes or [])
