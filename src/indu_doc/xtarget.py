import hashlib
from enum import Enum
from typing import List, Optional

from .attributed_base import AttributedBase
from .attributes import Attribute
from .configs import AspectsConfig
from .tag import Tag


class XTargetType(Enum):
    DEVICE = "device"
    STRIP = "strip"
    CABLE = "cable"
    OTHER = "other"  # Fallback type


class XTarget(AttributedBase):
    def __init__(
        self,
        tag: Tag,
        configs: AspectsConfig,
        target_type: XTargetType = XTargetType.OTHER,
        attributes: Optional[List[Attribute]] = None,
    ) -> None:
        super().__init__(attributes)
        self.tag: Tag = tag
        self.target_type: XTargetType = target_type
        self.configs: AspectsConfig = configs

    def add_attribute(self, attribute: Attribute) -> None:
        self.attributes.append(attribute)

    def remove_attribute(self, attr: Attribute) -> None:
        self.attributes = [
            attribute for attribute in self.attributes if attribute is not attr
        ]

    def get_attributes(self, name: str):
        return [attribute for attribute in self.attributes if attribute.name == name]

    def get_name(self) -> str:
        tag_parts = self.tag.get_tag_parts()
        if not tag_parts:
            return ""
        ordered_seps = self.configs.separators
        ordered_seps = [sep for sep in ordered_seps if sep in tag_parts]
        new_tag_str = "".join(
            [f"{sep}{tag_parts[sep]}" for sep in ordered_seps])
        return new_tag_str

    def get_unique_id(self) -> str:
        # Everytime we process the pdf -> generate the same ID for the same tag
        # The tag string should always be the same for the same object
        return hashlib.md5(self.tag.tag_str.encode()).hexdigest()

    def __repr__(self) -> str:
        return f"Object(tag={self.tag}, attributes={self.attributes})"
