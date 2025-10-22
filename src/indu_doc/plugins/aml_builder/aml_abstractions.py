from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeAlias
from datetime import datetime

import lxml.etree as et

import hashlib
import uuid
import json

import logging
logger = logging.getLogger(__name__)


GUID: TypeAlias = str


class ISerializeable(ABC):
    """
    Abstract base class for serializable AML concepts.

    This interface defines a standard contract for converting AML-related
    objects into XML representations. Any AML concept that needs to be stored, exchanged, or
    processed in AML format should implement this interface.

    """
    @abstractmethod
    def serialize(self) -> et._Element:
        """
        Serialize the AML concept into an XML element.

        :returns: The XML element representing the object.
        :rtype: xml.etree.ElementTree.Element
        """
        raise NotImplementedError("Serialize is not implemented")
    
    # @classmethod
    # @abstractmethod
    # def deserialize(cls, el: et._Element) -> "ISerializeable":
    #     raise NotImplementedError("Deserialize is not implemented")


@dataclass
class InternalAttribute(ISerializeable):
    """
    Represents an AML InternalElement attribute.

    :param name: Attribute name.
    :param value: Attribute value.
    :param data_type: AML data type (default: ``xs:string``).
    """
    name: str
    value: str
    data_type: str = "xs:string"  # TODO: for now all strings

    def serialize(self) -> et._Element:
        item = et.Element("Attribute")
        item.set("Name", self.name)
        item.set("AttributeDataType", self.data_type) 
        value = et.SubElement(item, "Value")
        value.text = self.value
        return item

class InternalLink(ISerializeable):
    """
    Represents an AML internal link connecting two external interfaces.

    :param refA: GUID of first linked external interface.
    :param refB: GUID of second linked external interface.
    """
    name: str
    refA: GUID
    refB: GUID

    def __init__(self, refA: "ExternalInterface", refB: "ExternalInterface"):
        # IDK what is name
        self.refA = refA.id
        self.refB = refB.id
        self.name = "ImALink"

    def serialize(self) -> et._Element:
        root = et.Element("InternalLink")
        root.set("RefPartnerSideA", self.refA)
        root.set("RefPartnerSideB", self.refB)
        root.set("Name", self.name)
        return root

class InternalElementBase(ISerializeable):
    """
    Base class representing AML internal element (IE). 
    All special IE cases must be based on this class.
    Provides GUID management.

    :param name: Element name.
    :param id: Unique element identifier (GUID).
    """
    name: str
    id: GUID

    guids: set[GUID] = set()

    def _create_guid(self, unq: dict[str, str]) -> GUID:
        """
        Create a deterministic GUID from a unique data dictionary.

        :param unq: Unique identifying data as dict.
        :return: Generated GUID string.
        """
        data_str = json.dumps(unq, sort_keys=True)  # ensure consistent order
        hash = hashlib.md5(data_str.encode("utf-8")).digest()
        guid = str(uuid.UUID(bytes=hash))
        return guid

    def _set_guid(self, guid: GUID):
        """
        Assign a GUID and also keep track of duplicates globally.

        :param guid: GUID to assign.
        """
        self.id = guid
        if self.id in InternalElementBase.guids:
            logger.warning(f"Non-unique ID detected: '{self.__class__}' '{self.id}'")
        InternalElementBase.guids.add(self.id)


class ExternalInterface(InternalElementBase):
    """
    Represents an AML external interface linked to an internal element.

    :param owner_guid: GUID of the owning internal element.
    :param role: Role or name of the interface.
    """

    def __init__(self, owner_guid: GUID, role: str):
        self.role = role
        self._set_guid(f"{owner_guid}:{role}")

    def serialize(self) -> et._Element:
        ext = et.Element("ExternalInterface")
        ext.set("Name", self.role)  # TODO IDK what name
        ext.set("ID", self.id)
        return ext
    

@dataclass
class TreeNode():
    """
    Represents a tree node for organizing AML internal elements into a tree.

    :param item: Stored element (optional).
    :param children: Child nodes indexed by string keys to ensure uniqueness.
    """

    item: InternalElementBase | None = None
    children: dict[str, "TreeNode"] = field(default_factory=dict)


class InstanceHierarchy(ISerializeable):
    """
    Represents an AML InstanceHierarchy structure. Has tree and links.

    :param name: Hierarchy name.
    :param version: Hierarchy version.
    :param tree: Root tree node containing internal elements.
    :param links: Optional list of internal links.
    """
    version: str
    name: str
    links: list[InternalLink] = []
    root: TreeNode

    def __init__(self, name: str, version: str, tree: TreeNode, links: list[InternalLink] = []):
        self.name = name
        self.version = version
        self.links = links
        self.root = tree

    def serialize(self) -> et._Element:
        root = et.Element("InstanceHierarchy")
        root.set("Name", self.name)
        version = et.SubElement(root, "Version")
        version.text = self.version
        # traverse tree

        def traverse_tree(el: et._Element, node: TreeNode):
            # el and node are same level
            for n in node.children.values():
                if n.item:
                    el.append(n.item.serialize())
                else:
                    raise ValueError("InternlNode is None")
                traverse_tree(el[-1], n)

        traverse_tree(root, self.root)
        #
        for link in self.links:
            root.append(link.serialize())

        return root
    


class CAEXFile(ISerializeable):
    """
    Represents a CAEX file root element (AML file) containing AML instance hierarchies.

    :param name: File name of the CAEX document.
    """
    hierarchies: list[InstanceHierarchy]
    name: str

    def __init__(self, name: str):
        self.name = name
        self.hierarchies = []

    def serialize(self) -> et._Element:
        root = self._create_root()
        for h in self.hierarchies:
            root.append(h.serialize())
        return root

    def _create_root(self) -> et._Element:
        XSI = "http://www.w3.org/2001/XMLSchema-instance"
        nsmap = {"xsi": XSI, None: "http://www.dke.de/CAEX"}
        root = et.Element("CAEXFile", nsmap=nsmap) # type: ignore
        # Just now are copy - allow to vary in the future if required
        root.set("SchemaVersion", "3.0")
        root.set("FileName", self.name)
        root.set(f"{{{XSI}}}schemaLocation",
                 "http://www.dke.de/CAEX CAEX_ClassModel_V.3.0.xsd")
        #
        version = et.SubElement(root, "SuperiorStandardVersion")
        version.text = "AutomationML 2.10"
        #
        src_info = et.SubElement(root, "SourceDocumentInformation")
        src_info.set("OriginName", "InduDoc Transformer")
        src_info.set("OriginVersion", "0.0.0")
        src_info.set(
            "OriginURL", "https://github.com/EPDF-Extractor/indu-doc-transformer")
        src_info.set("LastWritingDateTime", self._get_datetime())
        return root

    def _get_datetime(self) -> str:
        now = datetime.now().astimezone()
        return now.isoformat()
    