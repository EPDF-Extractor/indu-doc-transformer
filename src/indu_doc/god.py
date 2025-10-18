"""_summary_
This module contains the factory class for creating Different objects.
"""

from dataclasses import dataclass
import logging
from functools import cache
from typing import Any, Optional, Union
from collections import defaultdict
import threading

from indu_doc.attributes import Attribute, AttributeType, AvailableAttributes
from indu_doc.common_page_utils import PageInfo, PageError, ErrorType
from indu_doc.configs import AspectsConfig
from indu_doc.connection import Connection, Link, Pin
from indu_doc.tag import Tag, Aspect, try_parse_tag
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


SupportedMapObjects = Union[XTarget, Connection, Link, PageError]


class PagesObjectsMapper:
    """
    mapping between pages and objects (xtargets, connections, links)
    """

    def __init__(self) -> None:
        # many-to-many mapping
        self.page_to_objects: defaultdict[PageMapperEntry,
                                   set[SupportedMapObjects]] = defaultdict(set)
        self.object_to_pages: defaultdict[SupportedMapObjects,
                                   set[PageMapperEntry]] = defaultdict(set)
        self._lock = threading.Lock()

    def add_mapping(self, page_info: PageInfo, obj: SupportedMapObjects):
        page_num = page_info.page.number + 1 if page_info.page.number else -1
        file_path = page_info.page.parent.name if page_info.page.parent else "unknown"
        entry = PageMapperEntry(page_num, file_path)

        with self._lock:
            self.page_to_objects[entry].add(obj)
            self.object_to_pages[obj].add(entry)

    def get_pages_of_object(self, obj: SupportedMapObjects) -> set[PageMapperEntry]:
        return self.object_to_pages[obj].copy()

    def get_objects_in_page(self, page_number: int, file_path: str) -> set[SupportedMapObjects]:
        entry = PageMapperEntry(page_number, file_path)
        return self.page_to_objects[entry]


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
        self.aspects: dict[str, Aspect] = dict[str, Aspect]()
        self.pages_mapper = PagesObjectsMapper()
        
        # Fine-grained locks for each dictionary
        self._xtargets_lock = threading.Lock()
        self._connections_lock = threading.Lock()
        self._attributes_lock = threading.Lock()
        self._links_lock = threading.Lock()
        self._pins_lock = threading.Lock()
        self._tags_lock = threading.Lock()
        self._aspects_lock = threading.Lock()

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
        with self._attributes_lock:
            self.attributes[str(attribute)] = attribute
        return attribute

    def create_tag(self, tag_str: str, page_info: PageInfo):
        t = Tag.get_tag_with_footer(
            tag_str, page_info.page_footer, self.configs) if page_info.page_footer else Tag(tag_str, self.configs)
        if not t:
            logger.warning(f"Failed to create tag from string: {tag_str}")
            return None

        # check if tag not exists - create aspects for it
        aspects: dict[str, tuple[Aspect, ...]] = {}
        
        with self._tags_lock:
            tag_exists = t.tag_str in self.tags
        
        if not tag_exists:
            for sep, values in t.get_tag_parts().items():
                level_aspects: list[Aspect] = []
                for v in values:
                    aspect = self.create_aspect(f"{sep}{v}", page_info)
                    if not aspect:
                        logger.warning(f"Weird tag which can not be broken into aspects: {str(aspect)} in {tag_str}")
                        continue
                    level_aspects.append(aspect)

                if len(values) == 0:
                    # empty aspect
                    aspect = self.create_aspect(sep, page_info)
                    if not aspect:
                        logger.warning(f"Unexpected error creating aspect: {str(aspect)} in {tag_str}")
                        continue
                    level_aspects.append(aspect)
                
                aspects[sep] = tuple(level_aspects)

        # assign created aspects to a tag
        t.set_aspects(aspects)

        # cache tags by their string representation
        with self._tags_lock:
            return self.tags.setdefault(t.tag_str, t)


    def create_aspect(
        self,
        tag_str: str,
        page_info: PageInfo,
        attributes: Optional[tuple[Attribute, ...]] = None,
    ) -> Optional[Aspect]:
        #
        logger.info(
            f"create_aspect {tag_str}"
        )
        # Must use raw try_parse_tag as it will not create any empty stuff
        parts = try_parse_tag(tag_str, self.configs)
        if not parts:
            msg = f"Failed to create aspect with tag: '{tag_str}'"
            self.create_error(page_info, msg, error_type=ErrorType.WARNING)
            logger.warning(msg)
            return None
        
        sep, vals = next(iter(parts.items()))
        # now assert that has one sep and one value
        if len(parts) != 1 or len(vals) != 1:
            msg = f"Failed to create aspect with tag: '{tag_str}' - has composite structure"
            self.create_error(page_info, msg, error_type=ErrorType.WARNING)
            logger.warning(msg)
            return None
        
        aspect = Aspect(sep, vals[0], list(attributes or []))

        key = aspect.get_guid()
        with self._aspects_lock:
            if key in self.aspects and attributes:
                existing_aspect = self.aspects[key]
                # merge attributes & return
                for attr in attributes:
                    existing_aspect.add_attribute(attr)
                return existing_aspect

            return self.aspects.setdefault(key, aspect)


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
            msg = f"Failed to create xtarget with tag: {tag_str}"
            self.create_error(page_info, msg, error_type=ErrorType.WARNING)
            logger.warning(msg)
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
        
        with self._xtargets_lock:
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

    def create_pin(self, tag_pin: str, role: str, parentLink: Link) -> Optional[Pin]:
        # for example a tag like =B+A1:PIN1:PIN2 creates a chain of pins PIN1 -> PIN2
        pins_names = tag_pin.split(":")[1:]
        if not pins_names:
            logger.warning(f"Invalid pin tag: {tag_pin}")
            return None

        # TODO: what if pin name is empty?
        current_pin = None
        for pin in reversed(pins_names):
            current_pin = Pin(name=pin, child=current_pin,
                              role=role, parentLink=parentLink)

        if not current_pin:
            logger.warning(f"Failed to create pin from tag: {tag_pin}")
            return None

        with self._pins_lock:
            return self.pins.setdefault(current_pin.get_guid(), current_pin)

    def create_link(
        self,
        name: str,
        page_info: PageInfo,
        parent: Any = None,
        src_pin_name: Optional[str] = None,
        dest_pin_name: Optional[str] = None,
        attributes: Optional[tuple[Attribute, ...]] = None,
    ):
        logger.debug(
            f"create_link {name} {src_pin_name} {dest_pin_name} {attributes}"
        )

        if not (parent and src_pin_name and dest_pin_name):
            logger.warning(
                f"Cannot create link without parent connection and both pins: {name} {src_pin_name} {dest_pin_name}"
            )
            return None

        link = Link(
            name=name,
            src_pin_name=src_pin_name,
            parent=parent,
            dest_pin_name=dest_pin_name,
            attributes=list(attributes or []),
        )

        # if we had this link already, merge attributes and return existing one
        link_key = link.get_guid()

        with self._links_lock:
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
        
        with self._connections_lock:
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
            msg = f"Linked connection where one/no pins specified: `{pin_from}` `{pin_to}`"
            self.create_error(page_info, msg, error_type=ErrorType.WARNING)
            logger.warning(msg)
            return None
        if not (tag_from and tag_to):
            msg = f"Linked connection where one/no targets specified: `{tag_from}` `{tag_to}`"
            self.create_error(page_info, msg, error_type=ErrorType.WARNING)
            logger.warning(msg)
            return None
        # tag is cable tag. if none -> connection is in virtual cable
        connection = self.create_connection(
            tag, tag_from, tag_to, page_info=page_info
        )
        # if it has no pins -> has no links
        link = self.create_link(
            tag or "virtual_link",
            page_info,
            parent=connection,
            src_pin_name=pin_from,
            dest_pin_name=pin_to,
            attributes=attributes,
        )
        if not link:
            logger.warning(
                f"Failed to create link for connection with pins: {pin_from} {pin_to}")
            return None
        
        pin_obj_from = self.create_pin(pin_from, "src", link)
        pin_obj_to = self.create_pin(pin_to, "dst", link)
        if pin_obj_from:
            link.set_src_pin(pin_obj_from)
        if pin_obj_to:
            link.set_dest_pin(pin_obj_to)
        
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

    def create_error(self, page_info: PageInfo, message: str, error_type: ErrorType = ErrorType.UNKNOWN_ERROR):
        new_error = PageError(message=message, error_type=error_type)
        self.pages_mapper.add_mapping(page_info, new_error)

    def add_errors(self, page_info: PageInfo, errors: list[PageError]):
        for e in errors:
            self.pages_mapper.add_mapping(page_info, e)

    def __repr__(self):
        return f"God(configs={self.configs},\n xtargets={len(self.xtargets)},\n connections={len(self.connections)},\n attributes={len(self.attributes)},\n links={len(self.links)},\n pins={len(self.pins)},\n aspects={len(self.aspects)})"