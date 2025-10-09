from __future__ import annotations
import json
from abc import ABC, abstractmethod
from enum import Enum
import hashlib
from typing import Any, Union
import uuid

from indu_doc.common_utils import normalize_string


class Attribute(ABC):
    def __init__(self, name: str) -> None:
        self.name: str = name

    @abstractmethod
    def get_db_representation(self) -> str:
        """return a string representation suitable for database storage.

        Returns:
            str: A string representation suitable for database storage, can be JSON or other format.
        """
        pass

    @classmethod
    @abstractmethod
    def from_db_representation(cls, db_str: str) -> "Attribute":
        """Create an Attribute instance from its database string representation.

        Args:
            db_str (str): The string representation from the database.

        Returns:
            Attribute: An instance of Attribute or its subclass.
        """
        pass

    @abstractmethod
    def get_search_entries(self) -> dict[str, Any]:
        """Return a dictionary of field-value pairs that can be used for searching, e.g., in a search index.
        The idea is to extract relevant text from the attribute for search purposes and create a table inside the db for this.
        Returns:
            dict[str, Any]: A dictionary with field names as keys and their values for searching.
        """
        pass

    @classmethod
    @abstractmethod
    def get_value_type(cls) -> type:
        """Return the type of value this attribute holds.

        Returns:
            type: The type of value (e.g., str, int, list).
        """
        pass

    @abstractmethod
    def __hash__(self) -> int:
        pass

    @abstractmethod
    def __eq__(self, other) -> bool:
        pass

    @abstractmethod
    def get_guid(self) -> str:
        raise NotImplementedError("GET GUID NOT IMPLEMENTED")

    def __repr__(self) -> str:
        return f"Attribute(name={self.name})"


class SimpleAttribute(Attribute):
    """A simple attribute with a string value.
    Represents a basic attribute with a name and a string value.
    It can be used for connection colors, cross-sections, or other simple metadata.
    """

    def __init__(self, name: str, value: str) -> None:
        super().__init__(name)
        self.value: str = value

    def get_db_representation(self) -> str:
        return json.dumps({"name": self.name, "value": self.value})

    @classmethod
    def from_db_representation(cls, db_str: str) -> "SimpleAttribute":
        data = json.loads(db_str)
        return cls(name=data["name"], value=data["value"])

    def get_search_entries(self) -> dict[str, Any]:
        return {normalize_string(self.name): normalize_string(self.value)}

    @classmethod
    def get_value_type(cls) -> type:
        return str

    def __hash__(self) -> int:
        return hash((self.name, self.value))

    def __eq__(self, other) -> bool:
        if not isinstance(other, SimpleAttribute):
            return False
        return self.name == other.name and self.value == other.value

    def __repr__(self) -> str:
        return f"{self.name} : {self.value}"

    def get_guid(self) -> str:
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{self.value}".encode()).digest()))


class RoutingTracksAttribute(Attribute):
    """An attribute representing routing tracks.
    This attribute holds a list of routing tracks associated with an object.
    """

    def __init__(self, name: str, tracks: list[str] | str, sep=";") -> None:
        super().__init__(name)
        if isinstance(tracks, str):
            tracks = tracks.split(sep)
        self.tracks: list[str] = tracks
        self.sep = sep

    def get_db_representation(self) -> str:
        return json.dumps({"name": self.name, "tracks": self.tracks})

    @classmethod
    def from_db_representation(cls, db_str: str) -> "RoutingTracksAttribute":
        data = json.loads(db_str)
        return cls(name=data["name"], tracks=data["tracks"])

    def get_search_entries(self) -> dict[str, Any]:
        return {"tracks": self.tracks}

    @classmethod
    def get_value_type(cls) -> Any:
        return Union[list[str], str]

    def __hash__(self) -> int:
        return hash((self.name, tuple(self.tracks)))

    def __eq__(self, other) -> bool:
        if not isinstance(other, RoutingTracksAttribute):
            return False
        return self.name == other.name and self.tracks == other.tracks

    def __repr__(self) -> str:
        return f"Route: {self.tracks}"

    def get_guid(self) -> str:
        tracks_str = self.sep.join(sorted(self.tracks))
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{tracks_str}".encode()).digest()))


class PLCAddressAttribute(Attribute): 
    """An attribute representing PLC diagram '%' addresses and their params.
    """

    def __init__(self, address: str, meta: dict[str, str]) -> None:
        super().__init__(address)
        self.meta = meta


    def get_db_representation(self) -> str:
        return json.dumps({"name": self.name, "meta": self.meta})

    @classmethod
    def from_db_representation(cls, db_str: str) -> "PLCAddressAttribute":
        data = json.loads(db_str)
        return cls(address=data["name"], meta=data["meta"])

    def get_search_entries(self) -> list[str]:
        return list(self.meta.values())

    @classmethod
    def get_value_type(cls) -> type:
        return dict[str, str]

    def __hash__(self) -> int:
        return hash((self.name, self.meta))

    def __eq__(self, other) -> bool:
        if not isinstance(other, RoutingTracksAttribute):
            return False
        return False # temporality assume theyre unique; self.name == other.name and self.meta == other.meta

    def __repr__(self) -> str:
        return f"PLC conn {self.name}: {self.meta}"

    def get_guid(self) -> str:
        meta_str = ';'.join(f"{k}={v}" for k, v in sorted(self.meta.items()))
        return str(uuid.UUID(bytes=hashlib.md5(f"{self.name}:{meta_str}".encode()).digest()))


# IMP: please register new attributes here




class AttributeType(Enum):
    SIMPLE = "SimpleAttribute"
    ROUTING_TRACKS = "RoutingTracksAttribute"
    PLC_ADDRESS = "PLCAddress"


AvailableAttributes: dict[AttributeType, type[Attribute]] = {
    AttributeType.SIMPLE: SimpleAttribute,
    AttributeType.ROUTING_TRACKS: RoutingTracksAttribute,
}
