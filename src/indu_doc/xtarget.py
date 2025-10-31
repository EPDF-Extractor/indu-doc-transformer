"""
Cross-reference targets (XTargets) for document objects.

This module defines XTarget, which represents a cross-referenceable target in
industrial documentation such as devices, strips, cables, and other components.
Each target has a tag, type, and can have attributes attached.
"""

import hashlib
from enum import Enum
from typing import List, Optional, Any
import uuid

from indu_doc.common_utils import normalize_string

from .attributed_base import AttributedBase
from .attributes import Attribute
from .configs import AspectsConfig
from .tag import Tag


class XTargetType(Enum):
    """
    Enumeration of cross-reference target types.
    
    Defines the different types of objects that can be targets in the system.
    """
    DEVICE = "device"  #: Electrical device (motor, relay, etc.)
    STRIP = "strip"    #: Terminal strip or connector
    CABLE = "cable"    #: Cable or wire
    OTHER = "other"    #: Fallback type for unclassified objects


XTargetTypePriority = {  # higher value means higher priority
    XTargetType.CABLE: 3,
    XTargetType.DEVICE: 2,
    XTargetType.STRIP: 1,
    XTargetType.OTHER: 0,
}
"""
Priority mapping for target types.

Higher values indicate higher priority when resolving conflicts or
determining which type to use when multiple types are possible.
"""


class XTarget(AttributedBase):
    """
    Represents a cross-referenceable target in industrial documentation.
    
    An XTarget is any object that can be referenced in diagrams, such as
    devices, terminal strips, cables, etc. Each target has a tag that
    identifies it and a type that categorizes it.
    
    :param tag: The tag identifying this target
    :type tag: Tag
    :param configs: Configuration for aspect parsing
    :type configs: AspectsConfig
    :param target_type: The type of this target, defaults to XTargetType.OTHER
    :type target_type: XTargetType, optional
    :param attributes: Optional list of attributes, defaults to None
    :type attributes: Optional[List[Attribute]], optional
    """
    
    def __init__(
        self,
        tag: Tag,
        configs: AspectsConfig,
        target_type: XTargetType = XTargetType.OTHER,
        attributes: Optional[List[Attribute]] = None,
    ) -> None:
        """
        Initialize an XTarget.
        
        :param tag: The tag for this target
        :type tag: Tag
        :param configs: Aspect configuration
        :type configs: AspectsConfig
        :param target_type: Target type, defaults to XTargetType.OTHER
        :type target_type: XTargetType, optional
        :param attributes: Optional attributes, defaults to None
        :type attributes: Optional[List[Attribute]], optional
        """
        super().__init__(attributes)
        self.tag: Tag = tag
        self.target_type: XTargetType = target_type
        self.configs: AspectsConfig = configs

    def add_attribute(self, attribute: Attribute) -> None:
        """
        Add an attribute to this target.
        
        :param attribute: The attribute to add
        :type attribute: Attribute
        """
        self.attributes.add(attribute)

    def remove_attribute(self, attr: Attribute) -> None:
        """
        Remove an attribute from this target.
        
        :param attr: The attribute to remove
        :type attr: Attribute
        """
        self.attributes.discard(attr)

    def get_attributes(self, name: str):
        """
        Get all attributes with a specific name.
        
        :param name: The attribute name to search for
        :type name: str
        :return: List of matching attributes
        :rtype: list[Attribute]
        """
        return [attribute for attribute in self.attributes if attribute.name == name]

    def get_name(self) -> str:
        """
        Get the reconstructed name string for this target.
        
        Reconstructs the tag string from its parsed parts using the
        configured separator order.
        
        :return: The reconstructed tag string
        :rtype: str
        """
        tag_parts = self.tag.get_tag_parts()
        if not tag_parts:
            return ""
        ordered_seps = self.configs.separators
        ordered_seps = [sep for sep in ordered_seps if sep in tag_parts]

        def unjoin_seps(sep, vals):
            return "".join(sep + v for v in vals)
        new_tag_str = "".join(
            [unjoin_seps(sep, tag_parts[sep]) for sep in ordered_seps])
        return new_tag_str

    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this target.
        
        Every time we process the PDF, we generate the same ID for the same tag.
        The tag string should always be the same for the same object as it
        appears in the PDF.
        
        :return: A globally unique identifier string
        :rtype: str
        """
        # Everytime we process the pdf -> generate the same ID for the same tag
        # The tag string should always be the same for the same object -> It's how we see them in the PDF
        return str(uuid.UUID(bytes=hashlib.md5(self.tag.tag_str.encode("utf-8")).digest()))

    def __str__(self) -> str:
        """
        Return string representation showing the tag.
        
        :return: The tag string
        :rtype: str
        """
        return self.tag.tag_str

    def __repr__(self) -> str:
        """
        Return detailed string representation.
        
        :return: String showing tag and attributes
        :rtype: str
        """
        return f"Object(tag={self.tag}, attributes={self.attributes})"
    
    def __eq__(self, other: object) -> bool:
        """
        Check equality with another XTarget.
        
        :param other: Another object to compare with
        :return: True if tag, type, configs, and attributes are equal
        :rtype: bool
        """
        if not isinstance(other, XTarget):
            return False
        return (
            self.tag == other.tag and
            self.target_type == other.target_type and
            self.configs == other.configs and
            self.attributes == other.attributes
        )
    
    def __hash__(self) -> int:
        """
        Return hash value based on GUID.
        
        :return: Hash value
        :rtype: int
        """
        return hash(self.get_guid())
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert target to dictionary representation.
        
        :return: Dictionary with target data including tag, type, and attributes
        :rtype: dict[str, Any]
        """
        attrs = {}
        for attr in (self.attributes if self.attributes else []):
            attrs.update(attr.get_search_entries())
        return {
            "tag": normalize_string(self.tag.tag_str),
            "guid": self.get_guid(),
            "type": normalize_string(self.target_type.value),
            "attributes": attrs,
        }
