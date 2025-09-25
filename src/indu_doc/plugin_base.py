from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeAlias
from collections import defaultdict

from .god import God
from .xtarget import XTarget
from .attributes import Attribute, SimpleAttribute, RoutingTracksAttribute
from .configs import AspectsConfig, LevelConfig
from .connection import Connection, Link, Pin

import lxml.objectify as ob
import lxml.etree as et

import hashlib
import uuid
import json
from datetime import datetime, timezone, timedelta

class BuilderPlugin(ABC):
    @abstractmethod
    def process(self) -> None:
        pass

###################

GUID: TypeAlias = str


class ISerializeable(ABC):
    @abstractmethod
    def serialize(self) -> et._Element:
        pass

@dataclass
class InternalAttribute(ISerializeable):
    attr: Attribute

    def serialize(self) -> et._Element:
        item = et.Element("Attribute")
        item.set("Name", self.attr.name)
        item.set("AttributeDataType", "xs:string")  # TODO: for now all strings
        value = et.SubElement(item, "Value")
        match self.attr:
            case SimpleAttribute():
                value.text = str(self.attr.value)
            case RoutingTracksAttribute():
                value.text = str(self.attr.tracks)
            case _:
                raise ValueError(f"Unsupported attribute type")
        return item

class InternalLink(ISerializeable):
    name: str
    refA: GUID
    refB: GUID

    def __init__(self, refA: GUID, refB: GUID):
        # IDK what is name
        self.refA = refA
        self.refB = refB
        self.name = "ImALink"

    def serialize(self) -> et._Element:
        root = et.Element("InternalLink")
        root.set("RefPartnerSideA", self.refA) 
        root.set("RefPartnerSideB", self.refB)
        root.set("Name", self.name)
        return root

class InternalElementBase(ISerializeable):
    name: str
    id: GUID

    guids: set[GUID] = set()

    def create_guid(self, unq: dict[str, str]) -> GUID:
        data_str = json.dumps(unq, sort_keys=True) # ensure consistent order
        hash = hashlib.md5(data_str.encode("utf-8")).digest()
        guid = str(uuid.UUID(bytes=hash))
        return guid

    def set_guid(self, guid: GUID):
        self.id = guid
        if self.id in InternalElementBase.guids:
            print(f"Non-unique ID detected: {self.__class__} {self.id}") 
        InternalElementBase.guids.add(self.id)
    
    @abstractmethod
    def serialize(self) -> et._Element:
        raise NotImplementedError("Serialize is not implemented")

    @abstractmethod
    def _get_guid(self, salt = ""):
        raise NotImplementedError("Get guid is not implemented")

class InternalPin(InternalElementBase):
    def __init__(self, pin: Pin, link: Link):
        self.pin = pin
        # self.set_guid(self.create_guid({
        #     link.
        # }))

    def _get_guid(self, salt = "") -> GUID:
        data = {
            "name": str(self.pin.name), 
            "attributes": [str(a) for a in (self.pin.attributes or [])]
        }
        data_str = json.dumps(data, sort_keys=True) # ensure consistent order
        hash = hashlib.md5(data_str.encode("utf-8")).digest()
        return str(uuid.UUID(bytes=hash))

    def serialize(self) -> et._Element:
        root = et.Element("InternalElement")
        root.set("Name", f"ConnPoint {self.pin.name}") 
        root.set("ID", self.id)
        # Add all atributes
        for attr in self.pin.attributes:
            item = InternalAttribute(attr).serialize()
            root.append(item)
        # Add external interfaces (TODO generalize through ISerialize?)
        ext = et.SubElement(root, "ExternalInterface")
        ext.set("Name", "ConnectionPoint") # TODO IDK what name
        ext.set("ID", self.id) # TODO it has to be unq also?
        return root

# do not mix with InternalLink!
class InternalConnection(InternalElementBase):
    id_a: GUID
    id_b: GUID

    def __init__(self, link: Link):
        self.link = link
        self.id_a = self.id + ':' + link.src_pin.name
        self.id_b = self.id + ':' + link.dest_pin.name
    
    def serialize(self) -> et._Element:
        root = et.Element("InternalElement")
        root.set("Name", f"Connection {self.link.name}") 
        root.set("ID", self.id)
        # Add all atributes
        for attr in self.link.attributes:
            item = InternalAttribute(attr).serialize()
            root.append(item)

        # Add external interfaces (TODO generalize through ISerialize?)
        ext = et.SubElement(root, "ExternalInterface")
        ext.set("Name", "SideA") # TODO IDK what name
        ext.set("ID", self.id_a)

        ext = et.SubElement(root, "ExternalInterface")
        ext.set("Name", "SideB") # TODO IDK what name
        ext.set("ID", self.id_b)

        return root

class InternalAspectBase(InternalElementBase):
    prefix: str  # = separator
    bmk: str     # accumulated separators and levels
    name: str    # name of current level aspect

    def __init__(self, name: str, prefix: str, bmk: str):
        self.name = name
        self.prefix = prefix
        self.bmk = bmk
        super().__init__()

    def serialize(self) -> et._Element:
        root = et.Element("InternalElement")
        root.set("Name", self.name) 
        root.set("ID", self.id)

        if self.id is None:
            raise ValueError("Do not use InternalAspectBase directly! (id is not set)")

        # Add Prefix
        item = et.SubElement(root, "Attribute")
        item.set("Name", "Prefix")
        item.set("AttributeDataType", "xs:string")  # TODO: for now all strings
        et.SubElement(item, "Value").text = self.prefix

        # Add BMK
        item = et.SubElement(root, "Attribute")
        item.set("Name", "BMK")
        item.set("AttributeDataType", "xs:string")  # TODO: for now all strings
        et.SubElement(item, "Value").text = self.bmk

        return root

class InternalAspect(InternalAspectBase):
    # it is also an aspect but for the selected InstanceHierarchy. 
    # For ECAD it is "ECAD". This is also to make diamondID distinct from ID 
    # (for DiamondID it is empty and thus consistent over trees; other Internal elements do not appear in not ECAD InstanceHierarchies)
    perspective: str   
    diamondID: GUID

    def _get_guid(self) -> GUID:
        data = {
            "whoami": "InternalAspect",
            "prefix": self.prefix, 
            "name": self.name,
            "salt": self.perspective 
        }
        data_str = json.dumps(data, sort_keys=True) # ensure consistent order
        hash = hashlib.md5(data_str.encode("utf-8")).digest()
        return str(uuid.UUID(bytes=hash))

    def __init__(self, name: str, prefix: str, bmk: str, perspective: str):
        self.perspective = perspective
        super().__init__(name, prefix, bmk)
        # Now set diamondId (TODO I has to clear perspective - thats a dirty hack to fix)
        self.perspective = ""
        self.diamondID = self._get_guid()
        self.perspective = perspective
    
    def serialize(self) -> et._Element:
        root = super().serialize()
        # Add diamondID
        item = et.SubElement(root, "SourceObjectInformation")
        item.set("OriginID", "DiamondId")
        item.set("SourceObjID", self.diamondID)
        #
        return root

class InternalXTarget(InternalAspectBase): 
    xtarget: XTarget
    connections: list[InternalConnection]
    connPoints: list[InternalPin]
    # this one required to create ...OrientedReferenceDesignation stuff
    aspects: dict[str, str]

    def __init__(self, xtarget: XTarget, levels: dict[str, LevelConfig]):
        self.xtarget = xtarget
        self.connections = []
        self.connPoints = []
        # get distinct aspects 
        tag_parts = self.xtarget.tag.get_tag_parts()
        self.aspects: dict[str, str] = defaultdict(str)
        for sep, name in tag_parts.items():
            self.aspects[levels[sep].Aspect.lower()] += sep+name

    def set_base(self, base: InternalAspectBase):
        self.name = base.name
        self.bmk = base.bmk
        self.prefix = base.prefix
    
    def serialize(self) -> et._Element:
        if self.name is None:
            raise ValueError("Can not serialize InternalXTarget until InternalAspect base is set")
        
        root = super().serialize()
        # Add "[...]OrientedReferenceDesignation" stuff
        for aspect, name in self.aspects.items():
            item = et.SubElement(root, "Attribute")
            item.set("Name", f"{aspect}OrientedReferenceDesignation")
            item.set("AttributeDataType", "xs:string")
            et.SubElement(item, "Value").text = name

        # print("attributes")
        # print(self.xtarget)
        # Add all attributes
        for attr in self.xtarget.attributes:
            item = InternalAttribute(attr).serialize()
            root.append(item)
        # TODO now I assume cant have both connections and points 
        # Add pins TODO IDK what are two elements called Function
        # item = et.SubElement(root, "InternalElement") 
        # item.set("Name", "Function") 
        for cn in self.connections:
            root.append(cn.serialize())
        # Add links TODO IDK what are two elements called Function
        #item = et.SubElement(root, "InternalElement")
        for cp in self.connPoints:
            root.append(cp.serialize())

        return root


@dataclass
class TreeNode():
    item: InternalAspectBase | None = None
    children: dict[str, "TreeNode"] = field(default_factory=dict)

class InstanceHierarchy(ISerializeable):
    version: str
    name: str
    targets: list[InternalXTarget]
    links: list[InternalLink] = []
    levels: list[str]

    def __init__(self, name: str, version: str, levels: list[str], targets: list[InternalXTarget], links: list[InternalLink] = []):
        self.name = name
        self.version = version
        self.targets = targets
        self.links = links
        self.levels = levels
        #
        # form tree of objects by aspects. Level of the tree is aspect priority
        tags_parts = [(t, t.xtarget.tag.get_tag_parts()) for t in self.targets]   
        # 
        root = TreeNode()
        for t, parts in tags_parts:
            current = root
            accumulated_tag = ""
            for sep in self.levels:
                if sep in parts:
                    key = sep + parts[sep]
                    accumulated_tag += key
                    #
                    if key not in current.children:
                        current.children[key] = TreeNode(
                            InternalAspect(parts[sep], sep, accumulated_tag, self.name)
                        )
                    current = current.children[key]
            
            # at the leaf, promote aspect to target (only for ECAD)
            if self.name == "ECAD" and current.item:
                t.set_base(current.item)
                current.item = t

        self.root = root

    def serialize(self) -> et._Element:
        root = et.Element("InstanceHierarchy")
        root.set("Name", self.name)
        version = et.SubElement(root, "Version")
        version.text = self.version
        # traverse tree
        def traverse_tree(el: et._Element, node: TreeNode):
            # el and node are same level
            for n in node.children.values():
                if n.item is None:
                    raise ValueError("InternlNode is None")
                el.append(n.item.serialize())
                traverse_tree(el[-1], n)

        traverse_tree(root, self.root)
        # 
        for l in self.links:
            root.append(l.serialize())

        return root

class CAEXFile(ISerializeable):
    hierarchies: list[InstanceHierarchy]
    name: str

    def __init__(self, name: str):
        self.name = name
        self.hierarchies = []

    def serialize(self):
        root = self._create_root()
        for h in self.hierarchies:
            root.append(h.serialize())
        return root

    def _create_root(self) -> et._Element:
        XSI = "http://www.w3.org/2001/XMLSchema-instance"
        nsmap = {"xsi": XSI, None: "http://www.dke.de/CAEX"}
        root = et.Element("CAEXFile", nsmap = nsmap)
        # Just now are copy - allow to vary in the future if required
        root.set("SchemaVersion", "3.0") 
        root.set("FileName", self.name)
        root.set(f"{{{XSI}}}schemaLocation", "http://www.dke.de/CAEX CAEX_ClassModel_V.3.0.xsd") 
        #
        version = et.SubElement(root, "SuperiorStandardVersion")
        version.text = "AutomationML 2.10"
        #
        src_info = et.SubElement(root, "SourceDocumentInformation")
        src_info.set("OriginName", "InduDoc Transformer")
        src_info.set("OriginVersion", "0.0.0")
        src_info.set("OriginURL", "https://github.com/EPDF-Extractor/indu-doc-transformer")
        src_info.set("LastWritingDateTime", self._get_datetime())
        return root

    def _get_datetime(self) -> str:
        now = datetime.now().astimezone()
        return now.isoformat()


class AMLBuilder(BuilderPlugin):

    def __init__(self, god: God, configs: AspectsConfig) -> None:
        self.god = god
        self.configs = configs

    def process(self) -> None:
        file_name = "text.aml"
        file = CAEXFile(file_name)
        # TODO may be move to CAEXfile
        
        # Create a lookup map of xtargets
        xtarget_lookup = {xtarget.tag.tag_str: InternalXTarget(xtarget, self.configs.levels) for xtarget in self.god.xtargets.values()}
        internal_links: list[InternalLink] = []

        # unpack connections and links
        for connection in self.god.connections.values():
            src = xtarget_lookup.get(connection.src.tag.tag_str) if connection.src else None
            dst = xtarget_lookup.get(connection.dest.tag.tag_str) if connection.dest else None
            through = xtarget_lookup.get(connection.through.tag.tag_str) if connection.through else None
            # 
            for link in connection.links:
                src_pin = InternalPin(link.src_pin, src.id) if src else None
                dst_pin = InternalPin(link.dest_pin, dst.id) if dst else None

                if dst_pin is not None:
                    dst.connPoints.append(dst_pin)
                if src_pin is not None:
                    src.connPoints.append(src_pin)

                if through is not None:
                    through_conn = InternalConnection(link, through.id)
                    through.connections.append(through_conn)
                    # add InternalLinks src -> through; through -> dst
                    internal_links.append(InternalLink(src_pin.id, through_conn.id_a))
                    internal_links.append(InternalLink(through_conn.id_b, dst_pin.id))
                else:
                    # Add InternalLink: src -> dst
                    internal_links.append(InternalLink(src_pin.id, dst_pin.id))
        
        targets = list(xtarget_lookup.values())
        # ECAD tree InstanceHierarchy
        file.hierarchies.append(InstanceHierarchy("ECAD", "0.0.1", list(self.configs.levels.keys()), targets, internal_links))

        # For all aspects build trees
        aspects: dict[str, list[str]] = defaultdict(list)
        for sep, config in self.configs.levels.items():
            aspects[config.Aspect.lower()].append(sep)
        for aspect, levels in aspects.items():
            file.hierarchies.append(InstanceHierarchy(aspect.capitalize(), "0.0.1", levels, targets))

        # Save to file with 2-space indentation
        tree = et.ElementTree(file.serialize())
        tree.write(
            file_name,
            pretty_print=True,  
            xml_declaration=True,
            encoding="utf-8"
        )
    

if __name__ == "__main__":
    # Tests
    item = InternalAttribute(SimpleAttribute("test", "test value")).serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalLink("bcda-1234", "abcd-1234").serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalPin(Pin("A1", [SimpleAttribute("a", "a test value"), SimpleAttribute("b", "b test value")]), "").serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalConnection(Link(
        "Conn", 
        Pin("A1", [SimpleAttribute("a", "a test value"), SimpleAttribute("b", "b test value")]), 
        Pin("B2", [SimpleAttribute("c", "c test value"), SimpleAttribute("d", "d test value")]), 
        [SimpleAttribute("e", "e test value")]
    ), "").serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalAspect("A1", "=", "=A1", "ECAD").serialize()
    item1 = InternalAspect("A1", "=", "=A1", "functional").serialize()
    print(et.tostring(item, pretty_print=True))
    print(et.tostring(item1, pretty_print=True))

    #

    # Do a fullscale test now
    from .manager import Manager
    import logging
    logging.basicConfig(
        filename="myapp.log", encoding="utf-8", filemode="w", level=logging.INFO
    )
    manager = Manager.from_config_file("config.json")

    # TEST
    # from .tag import Tag
    # god = God(manager.configs)
    # god.xtargets.add(XTarget(Tag("=A+B-C", manager.configs), manager.configs, attributes=[SimpleAttribute("a", "a test value")]))
    # builder = AMLBuilder(god, manager.configs)
    # builder.process()
    # exit(0)

    #
    manager.process_pdfs("./pdfs/sample.pdf")

    import time
    from pathlib import Path

    def monitor_processing(manager: Manager) -> bool:
        last_progress = -1

        while True:
            state_info = manager.get_processing_state()
            state = state_info["state"]
            progress = state_info["progress"]

            if state == "idle":
                return True
            elif state == "error":
                print(
                    f"\nProcessing failed: {state_info['error_message']}")
                return False
            elif state in ["processing", "stopping"]:
                if progress["total_pages"] > 0:
                    current_progress = int(progress["percentage"] * 100)
                    if current_progress != last_progress:
                        print(
                            f"\rProgress: {current_progress:3d}% ({progress['current_page']}/{progress['total_pages']})")
                        last_progress = current_progress

                time.sleep(10)  

    success = monitor_processing(manager)
    if success:
        print(manager.get_stats())

        builder = AMLBuilder(manager.god, manager.configs)
        builder.process()


