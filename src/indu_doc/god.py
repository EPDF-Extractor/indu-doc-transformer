"""_summary_
This module contains the factory class for creating Different objects.
"""

from dataclasses import dataclass
import logging
from functools import cache
from typing import Any, Optional, Union


from indu_doc.attributes import Attribute, AttributeType, AvailableAttributes
from indu_doc.common_page_utils import PageInfo, PageType
from indu_doc.configs import AspectsConfig
from indu_doc.connection import Connection, Link, Pin
from indu_doc.tag import Tag
from indu_doc.xtarget import XTarget, XTargetType, XTargetTypePriority

logger = logging.getLogger(__name__)


def _is_pin_tag(tag: str) -> bool:
    # every pin for error handling starts from ':'
    return tag.find(':') != -1


def _split_pin_tag(tag_pin: str) -> tuple[str, Optional[str]]:
    # now I assume that pin starts from ':'
    tags = tag_pin.split(':', 1)
    # every pin for error handling starts from ':'
    return tags[0], None if len(tags) == 1 else ':' + tags[1]


@dataclass(frozen=True)
class PageMapperEntry:
    page_number: int
    # page_type: PageType
    file_path: str

    def __hash__(self) -> int:
        return hash((self.page_number, self.file_path))


SupportedMapObjects = Union[XTarget, Connection, Link]


class PagesObjectsMapper:
    """
    mapping between pages and objects (xtargets, connections, links)
    """

    def __init__(self) -> None:
        # many-to-many mapping
        self.page_to_objects: dict[PageMapperEntry,
                                   set[SupportedMapObjects]] = dict()
        self.object_to_pages: dict[SupportedMapObjects,
                                   set[PageMapperEntry]] = dict()

    def add_mapping(self, page_info: PageInfo, obj: SupportedMapObjects):
        page_num = page_info.page.number + 1 if page_info.page.number else -1
        file_path = page_info.page.parent.name if page_info.page.parent else "unknown"
        entry = PageMapperEntry(page_num, file_path)

        # add to both mappings
        self.page_to_objects[entry] = self.page_to_objects.get(entry, set())
        self.page_to_objects[entry].add(obj)

        self.object_to_pages[obj] = self.object_to_pages.get(obj, set())
        self.object_to_pages[obj].add(entry)

    def get_pages_of_object(self, obj: SupportedMapObjects) -> set[PageMapperEntry]:
        return self.object_to_pages.get(obj, set())

    def get_objects_in_page(self, page_number: int, file_path: str) -> set[SupportedMapObjects]:
        entry = PageMapperEntry(page_number, file_path)
        return self.page_to_objects.get(entry, set())


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
        self.pages_mapper = PagesObjectsMapper()

    def create_attribute(self, attribute_type: AttributeType, name: str, value: Any) -> Attribute:
        if attribute_type not in AvailableAttributes:
            raise ValueError(f"Unknown attribute type: {attribute_type}")

        attribute_cls: type[Attribute] = AvailableAttributes[attribute_type]
        # make sure value is of correct type
        # if not isinstance(value, attribute_cls.get_value_type()):
        #     raise ValueError(
        #         f"Value for attribute {name} must be of type {attribute_cls.get_value_type().__name__}"
        #     )
        attribute = attribute_cls(name, value)  # type: ignore
        self.attributes[str(attribute)] = attribute
        return attribute

    def create_tag(self, tag_str: str, page_info: PageInfo):
        t = Tag.get_tag_with_footer(
            tag_str, page_info.page_footer, self.configs) if page_info.page_footer else Tag(tag_str, self.configs)
        if not t:
            logger.warning(f"Failed to create tag from string: {tag_str}")
            return None

        # cache tags by their string representation
        return self.tags.setdefault(t.tag_str, t)

    def create_xtarget(
        self,
        tag_str: str,
        page_info: PageInfo,
        target_type: XTargetType = XTargetType.OTHER,
        attributes: Optional[tuple[Attribute, ...]] = None,
    ) -> Optional[XTarget]:
        # prohibit creation of xtargets with unparsed pins
        if _is_pin_tag(tag_str):
            logger.warning(f"XTarget tag has pins: {tag_str}")
            return None

        logger.debug(
            f"create_xtarget {tag_str}"
        )

        tag = self.create_tag(tag_str, page_info)
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
        target_key = xtarget.get_guid()
        if target_key in self.xtargets:
            # we have it already, merge attributes and use higher priority type
            # +A1:1 -> GUID(tag.tag_str)
            existing_xtarget = self.xtargets[target_key]
            new_type = target_type if XTargetTypePriority[target_type] > XTargetTypePriority[
                existing_xtarget.target_type] else existing_xtarget.target_type

            existing_xtarget.target_type = new_type

            if attributes:
                for attr in attributes:
                    existing_xtarget.add_attribute(attr)
            self.pages_mapper.add_mapping(page_info, existing_xtarget)
            return existing_xtarget

        new_xtarget = self.xtargets.setdefault(target_key, xtarget)
        self.pages_mapper.add_mapping(page_info, new_xtarget)
        return new_xtarget

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

    def create_link(
        self,
        name: str,
        page_info: PageInfo,
        parent: Any = None,
        src_pin: Optional[Pin] = None,
        dest_pin: Optional[Pin] = None,
        attributes: Optional[tuple[Attribute, ...]] = None,
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
        link_key = link.get_guid()

        if link_key in self.links:
            existing_link = self.links[link_key]
            if attributes:
                for attr in attributes:
                    existing_link.attributes.add(attr)

            self.pages_mapper.add_mapping(page_info, existing_link)
            return existing_link

        elink = self.links.setdefault(link_key, link)
        self.pages_mapper.add_mapping(page_info, elink)

        return elink

    def create_connection(
        self,
        tag: Optional[str],
        tag_from: str,
        tag_to: str,
        page_info: PageInfo,
        attributes: Optional[tuple[Attribute, ...]] = None
    ):
        logger.debug(
            f"create_connection at {tag}: {tag_from} -> {tag_to} {attributes}"
        )
        # tag is cable tag. if none -> connection is in virtual cable
        through = self.create_xtarget(
            tag,
            page_info,
            XTargetType.CABLE,
            attributes,
        ) if tag else None

        # TODO: send types of objects
        obj_from = self.create_xtarget(
            tag_from, page_info=page_info, target_type=XTargetType.DEVICE
        )
        obj_to = self.create_xtarget(
            tag_to, page_info=page_info, target_type=XTargetType.DEVICE
        )
        conn = Connection(src=obj_from, dest=obj_to, through=through, links=[])
        new_or_existing_conn = self.connections.setdefault(
            conn.get_guid(), conn)
        self.pages_mapper.add_mapping(page_info, new_or_existing_conn)

        return new_or_existing_conn

    def create_connection_with_link(
        self,
        tag: Optional[str],
        pin_tag_from: str,    # has shape tag:pin
        pin_tag_to: str,
        page_info: PageInfo,
        attributes: Optional[tuple[Attribute, ...]] = None
    ):
        logger.debug(
            f"create_connection_with_link at {tag}: '{pin_tag_from}' -> '{pin_tag_to}' {attributes}"
        )
        # Split pin_tag into tag & pin
        tag_from, pin_from = _split_pin_tag(pin_tag_from)
        tag_to, pin_to = _split_pin_tag(pin_tag_to)
        #
        if not (pin_from and pin_to):
            logger.warning(
                f"Linked connection where one/no pins specified: {pin_from} {pin_to}")
            return None
        if not (tag_from and tag_to):
            logger.warning(
                f"Linked connection where one/no targets specified: {tag_from} {tag_to}")
            return None
        # tag is cable tag. if none -> connection is in virtual cable
        connection = self.create_connection(
            tag, tag_from, tag_to, page_info=page_info
        )
        # if it has no pins -> has no links
        pin_obj_from = self.create_pin(pin_from)
        pin_obj_to = self.create_pin(pin_to)
        link = self.create_link(
            tag or "virtual_link",
            page_info,
            parent=connection,
            src_pin=pin_obj_from,
            dest_pin=pin_obj_to,
            attributes=attributes,
        )
        connection.add_link(link)

        # already in dict from create_connection
        return connection

    def get_objects_on_page(self, page_num: int, file_path: str) -> set[SupportedMapObjects]:
        return self.pages_mapper.get_objects_in_page(page_num, file_path)

    def get_pages_of_object(self, obj: SupportedMapObjects | str) -> set[PageMapperEntry]:
        """
        Get pages where the object appears.
        If obj is a string, try to find the object by its GUID or string representation.

        """
        if isinstance(obj, str):
            # try to find object by its string representation
            if obj in self.xtargets:
                obj = self.xtargets[obj]
            elif obj in self.connections:
                obj = self.connections[obj]
            elif obj in self.links:
                obj = self.links[obj]
            else:
                logger.warning(f"Object not found for string: {obj}")
                return set()

        return self.pages_mapper.get_pages_of_object(obj)

    def __repr__(self):
        return f"God(configs={self.configs},\n xtargets={len(self.xtargets)},\n connections={len(self.connections)},\n attributes={len(self.attributes)},\n links={len(self.links)},\n pins={len(self.pins)})"
