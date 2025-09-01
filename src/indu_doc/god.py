"""_summary_
This module contains the factory class for creating Different objects.
"""

import logging
from functools import cache
from typing import Any, Optional

from .attributes import Attribute, AttributeType, AvailableAttributes
from .configs import AspectsConfig
from .connection import Connection, Link, Pin
from .xtarget import XTarget, XTargetType
from .tag import Tag

logger = logging.getLogger(__name__)


class God:
    """
    Factory class for creating different objects.
    It's just a container for static methods, no instance of this class should be created.
    """

    def __init__(self, configs: AspectsConfig):
        self.configs: AspectsConfig = configs
        self.xtargets: set[XTarget] = set()
        self.connections: set[Connection] = set()
        self.attributes: set[Attribute] = set()
        self.links: set[Link] = set()
        self.pins: set[Pin] = set()

    @cache
    def create_attribute(self, attribute_type: AttributeType, name: str, value: Any) -> Attribute:
        if attribute_type not in AvailableAttributes:
            raise ValueError(f"Unknown attribute type: {attribute_type}")

        attribute_cls = AvailableAttributes[attribute_type]
        # make sure value is of correct type
        if not isinstance(value, attribute_cls.get_value_type()):
            raise ValueError(
                f"Value for attribute {name} must be of type {attribute_cls.get_value_type().__name__}"
            )
        attribute = attribute_cls(name, value)
        self.attributes.add(attribute)
        return attribute

    @cache
    def create_tag(self, tag_str: str, footer=None):
        if footer:
            return Tag.get_tag_with_footer(tag_str, footer, self.configs)
        else:
            return Tag(tag_str, self.configs)

    @cache
    def create_xtarget(
        self,
        tag_str: str,
        target_type: XTargetType = XTargetType.OTHER,
        footer=None,
        attributes: Optional[tuple[Attribute]] = None,
    ):
        tag = self.create_tag(tag_str, footer)
        xtarget = XTarget(
            tag=tag,
            configs=self.configs,
            target_type=target_type,
            attributes=list(attributes or []),
        )
        self.xtargets.add(xtarget)
        return xtarget

    @cache
    def create_pin(self, tag_pin: str) -> Optional[Pin]:
        terminal_index = tag_pin.find(":")
        if terminal_index == -1:
            logger.warning(f"Invalid pin tag: {tag_pin}")
            return None

        pin_part = tag_pin[terminal_index + 1:]
        pins_names = pin_part.split(":")
        if not pins_names:
            logger.warning(f"Invalid pin tag: {tag_pin}")
            return None

        current_pin = None
        for pin in reversed(pins_names):
            current_pin = Pin(name=pin, child=current_pin)
            self.pins.add(current_pin)
        return (
            current_pin  # this is the first pin in the chain, get all children from it
        )

    @cache
    def create_link(
        self,
        name: str,
        src_pin: Optional[Pin] = None,
        dest_pin: Optional[Pin] = None,
        attributes: Optional[tuple[Attribute]] = None,
    ):
        link = Link(
            name=name,
            src_pin=src_pin,
            dest_pin=dest_pin,
            attributes=list(attributes or []),
        )
        self.links.add(link)
        return link

    @cache
    def create_connection_no_links(
        self, tag: Optional[str], pin_tag_from: str, pin_tag_to: str, footer=None
    ):
        # tag is cable tag. if none -> connection is in virtual cable
        through = (
            self.create_xtarget(
                tag_str=tag,
                target_type=XTargetType.CABLE if tag else XTargetType.OTHER,
                footer=footer,
            )
            if tag
            else None
        )
        # TODO: send types of objects
        obj_from = self.create_xtarget(
            tag_str=pin_tag_from, target_type=XTargetType.DEVICE, footer=footer
        )
        obj_to = self.create_xtarget(
            tag_str=pin_tag_to, target_type=XTargetType.DEVICE, footer=footer
        )
        return Connection(src=obj_from, dest=obj_to, through=through, links=[])

    @cache
    def create_connection(
        self,
        tag: Optional[str],
        pin_tag_from: str,
        pin_tag_to: str,
        attributes: Optional[tuple[Attribute]] = None,
        footer=None,
    ):
        # tag is cable tag. if none -> connection is in virtual cable
        connection = self.create_connection_no_links(
            tag, pin_tag_from, pin_tag_to, footer
        )
        pin_from = self.create_pin(pin_tag_from)
        pin_to = self.create_pin(pin_tag_to)
        link = self.create_link(
            name=tag or "virtual_link",
            src_pin=pin_from,
            dest_pin=pin_to,
            attributes=attributes,
        )
        connection.add_link(link)
        self.connections.add(connection)
        return connection

    def __repr__(self):
        return f"God(configs={self.configs},\n xtargets={len(self.xtargets)},\n connections={len(self.connections)},\n attributes={len(self.attributes)},\n links={len(self.links)},\n pins={len(self.pins)})"
