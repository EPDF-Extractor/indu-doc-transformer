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
        attributes: Optional[tuple[Attribute]] = None,
        footer=None,
    ):
        # prohibit creation of xtargets with unparsed pins
        if self._is_pin_tag(tag_str):
            logger.warning(f"XTarget tag has pins: {tag_str}")
            return None
        logger.debug(
            f"create_xtarget {tag_str}"
        )
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
        pins_names = tag_pin.split(":")[1:]
        if not pins_names:
            logger.warning(f"Invalid pin tag: {tag_pin}")
            return None
        # TODO: what if pin name is empty?
        current_pin = None
        for pin in reversed(pins_names):
            current_pin = Pin(name=pin, child=current_pin)
            self.pins.add(current_pin)
        return (
            current_pin  # this is the first pin in the chain, get all children from it
        )
    
    def _is_pin_tag(self, tag: str) -> bool:
        # every pin for error handling starts from ':'
        return tag.find(':') != -1
    

    def _split_pin_tag(self, tag_pin: str) -> tuple[str, Optional[str]]:
        # now I assume that pin starts from ':'
        tags = tag_pin.split(':', 1)
        # every pin for error handling starts from ':'
        return (tags[0], None if len(tags) == 1 else ':' + tags[1])

    @cache
    def create_link(
        self,
        name: str,
        src_pin: Optional[Pin] = None,
        dest_pin: Optional[Pin] = None,
        attributes: Optional[tuple[Attribute]] = None,
    ):
        logger.debug(
            f"create_link {name} {src_pin} {dest_pin}"
        )
        link = Link(
            name=name,
            src_pin=src_pin,
            dest_pin=dest_pin,
            attributes=list(attributes or []),
        )
        self.links.add(link)
        return link

    @cache
    def create_connection(
        self, 
        tag: Optional[str], 
        tag_from: str, 
        tag_to: str, 
        attributes: Optional[tuple[Attribute]] = None, 
        footer=None
    ):
        #
        logger.debug(
            f"create_connection at {tag}: {tag_from} -> {tag_to} {attributes}"
        )
        # tag is cable tag. if none -> connection is in virtual cable
        through = (
            self.create_xtarget(
                tag,
                XTargetType.CABLE,
                attributes,
                footer,
            )
            if tag
            else None
        )
        # TODO: send types of objects
        obj_from = self.create_xtarget(
            tag_from, XTargetType.DEVICE, footer=footer
        )
        obj_to = self.create_xtarget(
            tag_to, XTargetType.DEVICE, footer=footer
        )
        return Connection(src=obj_from, dest=obj_to, through=through, links=[])

    @cache
    def create_connection_with_link(
        self,
        tag: Optional[str],
        pin_tag_from: str,    # has shape tag:pin
        pin_tag_to: str,
        attributes: Optional[tuple[Attribute]] = None,
        footer=None,
    ):
        logger.debug(
            f"create_connection_with_link at {tag}: {pin_tag_from} -> {pin_tag_to} {attributes}"
        )
        # Split pin_tag into tag & pin
        tag_from, pin_from = self._split_pin_tag(pin_tag_from)
        tag_to, pin_to = self._split_pin_tag(pin_tag_to)
        # 
        if not (pin_from and pin_to):
            logger.warning(f"Linked connection where one/no pins specified: {pin_from} {pin_to}")
            return None
        # tag is cable tag. if none -> connection is in virtual cable
        connection = self.create_connection(
            tag, tag_from, tag_to, footer=footer
        )
        # if has no pins -> has no links 
        pin_obj_from = self.create_pin(pin_from)
        pin_obj_to = self.create_pin(pin_to)
        link = self.create_link(
            name=tag or "virtual_link",
            src_pin=pin_obj_from,
            dest_pin=pin_obj_to,
            attributes=attributes,
        )
        connection.add_link(link)
        self.connections.add(connection)
        return connection

    def __repr__(self):
        return f"God(configs={self.configs},\n xtargets={len(self.xtargets)},\n connections={len(self.connections)},\n attributes={len(self.attributes)},\n links={len(self.links)},\n pins={len(self.pins)})"
