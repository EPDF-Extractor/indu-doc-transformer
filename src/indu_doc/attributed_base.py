from abc import ABC, abstractmethod
from functools import cache
from typing import Optional

from .attributes import Attribute


class AttributedBase(ABC):
    def __init__(self, attributes: Optional[list[Attribute]]) -> None:
        self.attributes: set[Attribute] = set(attributes or [])

    @abstractmethod
    @cache
    def get_guid(self) -> str:
        raise NotImplementedError("GET GUID NOT IMPLEMENTED")
