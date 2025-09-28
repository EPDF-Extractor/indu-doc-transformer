"""_summary_
This module contains the factory class for creating Different objects.
"""

import logging
from functools import cache
from typing import Any, Optional

from indu_doc.attributes import Attribute, AttributeType, AvailableAttributes
from indu_doc.configs import AspectsConfig
from indu_doc.connection import Connection, Link, Pin
from indu_doc.xtarget import XTarget, XTargetType, XTargetTypePriority
from indu_doc.tag import Tag

logger = logging.getLogger(__name__)


class God:
    """
    Factory class for creating different objects.
    Operates:
    - xtargets
    - connections
    - attributes
    - connections
    - links
    - pins
    """

    def __init__(self, configs: AspectsConfig):
        self.configs: AspectsConfig = configs
        self.xtargets: dict[str, XTarget] = dict[str, XTarget]()
        self.connections: dict[str, Connection] = dict[str, Connection]()
        self.attributes: dict[str, Attribute] = dict[str, Attribute]()
        self.links: dict[str, Link] = dict[str, Link]()
        self.pins: dict[str, Pin] = dict[str, Pin]()
        self.tags: dict[str, Tag] = dict[str, Tag]()

    @cache
    def create_attribute(self, attribute_type: AttributeType, name: str, value: Any) -> Attribute:
        if attribute_type not in AvailableAttributes:
            raise ValueError(f"Unknown attribute type: {attribute_type}")

        attribute_cls: type[Attribute] = AvailableAttributes[attribute_type]
        # make sure value is of correct type
        if not isinstance(value, attribute_cls.get_value_type()):
            raise ValueError(
                f"Value for attribute {name} must be of type {attribute_cls.get_value_type().__name__}"
            )
        attribute = attribute_cls(name, value)  # type: ignore
        self.attributes[str(attribute)] = attribute
        return attribute

    @cache
    def create_tag(self, tag_str: str, footer=None):
        t = Tag.get_tag_with_footer(
            tag_str, footer, self.configs) if footer else Tag(tag_str, self.configs)
        if not t:
            logger.warning(f"Failed to create tag from string: {tag_str}")
            return None

        # cache tags by their string representation
        return self.tags.setdefault(t.tag_str, t)

    @cache
    def create_xtarget(
        self,
        tag_str: str,
        target_type: XTargetType = XTargetType.OTHER,
        attributes: Optional[tuple[Attribute]] = None,
        footer=None,
    ) -> Optional[XTarget]:
        # prohibit creation of xtargets with unparsed pins
        if self._is_pin_tag(tag_str):
            logger.warning(f"XTarget tag has pins: {tag_str}")
            return None
        logger.debug(
            f"create_xtarget {tag_str}"
        )
        tag = self.create_tag(tag_str, footer)
        if not tag:
            logger.warning(f"Failed to create xtarget with tag: {tag_str}")
            return None

            # create new xtarget
        xtarget = XTarget(
            tag=tag,
            configs=self.configs,
            target_type=target_type,
            attributes=list(attributes or []),
        )
        # Now that we have a valid tag, create the xtarget, lets see if it exists already
        Target_key = xtarget.get_guid()
        if Target_key in self.xtargets:
            # we have it already, merge attributes and use higher priority type
            # +A1:1 -> GUID(tag.tag_str)
            existing_xtarget = self.xtargets[Target_key]
            new_type = target_type if XTargetTypePriority[target_type] > XTargetTypePriority[
                existing_xtarget.target_type] else existing_xtarget.target_type

            existing_xtarget.target_type = new_type

            if attributes:
                for attr in attributes:
                    existing_xtarget.add_attribute(attr)

            return existing_xtarget

        return self.xtargets.setdefault(Target_key, xtarget)

    def create_pin(self, tag_pin: str) -> Optional[Pin]:
        # for example a tag like =B+A1:PIN1:PIN2 creates a chain of pins PIN1 -> PIN2
        pins_names = tag_pin.split(":")[1:]
        if not pins_names:
            logger.warning(f"Invalid pin tag: {tag_pin}")
            return None

        # TODO: what if pin name is empty?
        current_pin = None
        for pin in reversed(pins_names):
            current_pin = Pin(name=pin, child=current_pin)

        if not current_pin:
            logger.warning(f"Failed to create pin from tag: {tag_pin}")
            return None

        return (
            # this is the first pin in the chain, get all children from it
            self.pins.setdefault(current_pin.get_id(), current_pin)
        )

    def _is_pin_tag(self, tag: str) -> bool:
        # every pin for error handling starts from ':'
        return tag.find(':') != -1

    def _split_pin_tag(self, tag_pin: str) -> tuple[str, Optional[str]]:
        # now I assume that pin starts from ':'
        tags = tag_pin.split(':', 1)
        # every pin for error handling starts from ':'
        return (tags[0], None if len(tags) == 1 else ':' + tags[1])

    def create_link(
        self,
        name: str,
        parent: Any = None,
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
            parent=parent,
            dest_pin=dest_pin,
            attributes=list(attributes or []),
        )

        # if we had this link already, merge attributes and return existing one
        Linkkey = link.get_guid()

        if Linkkey in self.links:
            existing_link = self.links[Linkkey]
            if attributes:
                for attr in attributes:
                    existing_link.attributes.add(attr)
            return existing_link

        return self.links.setdefault(Linkkey, link)

    @cache
    def create_connection(
        self,
        tag: Optional[str],
        tag_from: str,
        tag_to: str,
        attributes: Optional[tuple[Attribute]] = None,
        footer=None
    ):
        logger.debug(
            f"create_connection at {tag}: {tag_from} -> {tag_to} {attributes}"
        )
        # tag is cable tag. if none -> connection is in virtual cable
        through = self.create_xtarget(
            tag,
            XTargetType.CABLE,
            attributes,
            footer,
        ) if tag else None

        # TODO: send types of objects
        obj_from = self.create_xtarget(
            tag_from, XTargetType.DEVICE, footer=footer
        )
        obj_to = self.create_xtarget(
            tag_to, XTargetType.DEVICE, footer=footer
        )
        conn = Connection(src=obj_from, dest=obj_to, through=through, links=[])

        return self.connections.setdefault(conn.get_guid(), conn)

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
            logger.warning(
                f"Linked connection where one/no pins specified: {pin_from} {pin_to}")
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
            parent=connection,
            src_pin=pin_obj_from,
            dest_pin=pin_obj_to,
            attributes=attributes,
        )
        connection.add_link(link)

        # already in dict from create_connection
        return connection

    def __repr__(self):
        return f"God(configs={self.configs},\n xtargets={len(self.xtargets)},\n connections={len(self.connections)},\n attributes={len(self.attributes)},\n links={len(self.links)},\n pins={len(self.pins)})"
