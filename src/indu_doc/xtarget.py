from functools import cache
import hashlib
from enum import Enum
from typing import List, Optional
import uuid

from .attributed_base import AttributedBase
from .attributes import Attribute
from .configs import AspectsConfig
from .tag import Tag


class XTargetType(Enum):
    DEVICE = "device"
    STRIP = "strip"
    CABLE = "cable"
    OTHER = "other"  # Fallback type


XTargetTypePriority = {  # higher value means higher priority
    XTargetType.CABLE: 3,
    XTargetType.DEVICE: 2,
    XTargetType.STRIP: 1,
    XTargetType.OTHER: 0,
}


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
        self.attributes.add(attribute)

    def remove_attribute(self, attr: Attribute) -> None:
        self.attributes.discard(attr)

    def get_attributes(self, name: str):
        return [attribute for attribute in self.attributes if attribute.name == name]

    def get_name(self) -> str:
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

    @cache
    def get_guid(self) -> str:
        # Everytime we process the pdf -> generate the same ID for the same tag
        # The tag string should always be the same for the same object -> It's how we see them in the PDF
        return str(uuid.UUID(bytes=hashlib.md5(self.tag.tag_str.encode("utf-8")).digest()))

    def __str__(self) -> str:
        return self.tag.tag_str

    def __repr__(self) -> str:
        return f"Object(tag={self.tag}, attributes={self.attributes})"
