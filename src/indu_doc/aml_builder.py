from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeAlias
from collections import defaultdict

from .god import God
from .xtarget import XTarget
from .attributes import Attribute, SimpleAttribute, RoutingTracksAttribute, PLCAddressAttribute
from .configs import AspectsConfig, LevelConfig
from .connection import Connection, Link, Pin
from .tag import Tag, Aspect

import lxml.objectify as ob
import lxml.etree as et

import hashlib
import uuid
import json
from datetime import datetime

import logging
logger = logging.getLogger(__name__)

###################

GUID: TypeAlias = str


class ISerializeable(ABC):
    @abstractmethod
    def serialize(self) -> et._Element:
        raise NotImplementedError("Serialize is not implemented")


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
            case PLCAddressAttribute():
                value.text = str(self.attr.meta)
            case _:
                raise ValueError(f"Unsupported attribute type")
        return item

class InternalLink(ISerializeable):
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
    name: str
    id: GUID

    guids: set[GUID] = set()

    def _create_guid(self, unq: dict[str, str]) -> GUID:
        data_str = json.dumps(unq, sort_keys=True)  # ensure consistent order
        hash = hashlib.md5(data_str.encode("utf-8")).digest()
        guid = str(uuid.UUID(bytes=hash))
        return guid

    def _set_guid(self, guid: GUID):
        self.id = guid
        if self.id in InternalElementBase.guids:
            logger.warning(f"Non-unique ID detected: '{self.__class__}' '{self.id}'")
        InternalElementBase.guids.add(self.id)


class ExternalInterface(InternalElementBase):
    def __init__(self, owner_guid: GUID, role: str):
        self.role = role
        self._set_guid(f"{owner_guid}:{role}")

    def serialize(self) -> et._Element:
        ext = et.Element("ExternalInterface")
        ext.set("Name", self.role)  # TODO IDK what name
        ext.set("ID", self.id)
        return ext


class InternalPin(InternalElementBase):
    pin: Pin
    external: ExternalInterface  # ExternalInterface requires unique ID also

    def __init__(self, pin: Pin):
        self.pin = pin
        self._set_guid(self.pin.get_guid())
        self.external = ExternalInterface(self.id, "ConnectionPoint")

    def serialize(self) -> et._Element:
        if self.id is None:
            raise ValueError("Can not serialize with no ID")
        root = et.Element("InternalElement")
        root.set("Name", f"ConnPoint {self.pin.name}")
        root.set("ID", self.id)
        # Add all atributes
        for attr in self.pin.attributes:
            item = InternalAttribute(attr).serialize()
            root.append(item)
        # Add external interface
        root.append(self.external.serialize())
        return root


class InternalConnection(InternalElementBase):
    # do not mix with InternalLink!
    external_a: ExternalInterface
    external_b: ExternalInterface

    def __init__(self, link: Link):
        self.link = link
        self._set_guid(link.get_guid())
        self.external_a = ExternalInterface(self.id, "SideA")
        self.external_b = ExternalInterface(self.id, "SideB")

    def serialize(self) -> et._Element:
        if self.id is None:
            raise ValueError("Can not serialize with no ID")
        root = et.Element("InternalElement")
        root.set("Name", f"Connection {self.link.name}")
        root.set("ID", self.id)
        # Add all atributes
        for attr in self.link.attributes:
            item = InternalAttribute(attr).serialize()
            root.append(item)

        # Add external interfaces
        root.append(self.external_a.serialize())
        root.append(self.external_b.serialize())

        return root

# TODO might not need it if BMK for XTargets is allowed (currently as a bug theyre allowed)

class InternalAspectBase(InternalElementBase):
    prefix: str  # = separator
    bmk: str     # accumulated separators and levels
    name: str    # name of current level aspect
    base: "InternalAspectBase | None" = None

    def __init__(self, aspect: Aspect, base: "InternalAspectBase | None" = None):
        self.aspect = aspect
        self.name = aspect.value
        self.prefix = aspect.separator
        self.base = base
        # accumulate bmk
        self.bmk = (base.bmk if base else "") + str(aspect)
        # accumulate guid (can not use aspect ID as it is non unique)
        self.id = self._create_guid({
            "prefix": self.prefix,
            "name": self.name,
            "base": self.base.id if self.base else ""
        })

    def serialize(self) -> et._Element:
        if self.__class__ == type(InternalAspectBase):
            raise ValueError("Do not serialize InternalAspectBase directly")

        root = et.Element("InternalElement")
        root.set("Name", self.name)
        root.set("ID", self.id)

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

    def __init__(self, perspective: str, aspect: Aspect, base: "InternalAspectBase | None" = None):
        super().__init__(aspect, base)
        # set diamondId
        self.diamondID = aspect.get_guid()
        # Update ID based on perspective (make unq across trees)
        self.perspective = perspective
        unq = {  # do not copy to reuse!
            "base": self.id,
            "salt": self.perspective
        }
        self._set_guid(self._create_guid(unq))  # will override self.id and check uniqueness

    def serialize(self) -> et._Element:
        root = super().serialize()
        # Add diamondID
        item = et.SubElement(root, "SourceObjectInformation")
        item.set("OriginID", "DiamondId")
        item.set("SourceObjID", self.diamondID)
        # Add all atributes
        for attr in self.aspect.attributes:
            item = InternalAttribute(attr).serialize()
            root.append(item)
        #
        return root


class InternalXTarget(InternalElementBase):
    xtarget: XTarget
    connections: list[InternalConnection]
    connPoints: list[InternalPin]
    # this one required to create ...OrientedReferenceDesignation stuff
    aspects: dict[str, str]
    #
    base: InternalAspectBase | None

    serialized: bool = False

    def __init__(self, xtarget: XTarget, levels: dict[str, LevelConfig]):
        self.xtarget = xtarget
        self._set_guid(xtarget.get_guid())
        self.connections = []
        self.connPoints = []
        self.base = None
        # get distinct aspects
        tag_parts = self.xtarget.tag.get_tag_parts()
        self.aspects: dict[str, str] = defaultdict(str)
        for sep, names in tag_parts.items():
            self.aspects[levels[sep].Aspect.lower()] += "".join(sep +
                                                                n for n in names)

    def set_base(self, base: InternalAspectBase):
        self.base = base

    def serialize(self) -> et._Element:
        if self.base is None:
            raise ValueError(
                "Can not serialize InternalXTarget until InternalAspect base is set")
        root = self.base.serialize()
        root.set("ID", self.id)  # override Aspect GUID with XTarget GUID
        # Add "[...]OrientedReferenceDesignation" stuff
        for aspect, name in self.aspects.items():
            item = et.SubElement(root, "Attribute")
            item.set("Name", f"{aspect}OrientedReferenceDesignation")
            item.set("AttributeDataType", "xs:string")
            et.SubElement(item, "Value").text = name

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
        # item = et.SubElement(root, "InternalElement")
        for cp in self.connPoints:
            root.append(cp.serialize())

        self.serialized = True

        return root


@dataclass
class TreeNode():
    item: InternalAspect | None = None
    leaf: InternalXTarget | None = None
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
        root = TreeNode()
        for t in self.targets:
            parts = t.xtarget.tag.get_aspects()
            # build tree
            current = root
            for sep in self.levels:
                if sep in parts:
                    for aspect in parts[sep]: # composite tag (multiple instances of same sep)
                        key = str(aspect)
                        if key not in current.children:
                            current.children[key] = TreeNode(
                                InternalAspect(
                                    self.name,
                                    aspect,
                                    current.item
                                )
                            )
                        current = current.children[key]

            # at the leaf, promote aspect to target (only for ECAD)
            if self.name == "ECAD" and current.item:
                t.set_base(current.item)
                current.leaf = t

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
                if n.leaf:
                    el.append(n.leaf.serialize())
                elif n.item:
                    el.append(n.item.serialize())
                else:
                    raise ValueError("InternlNode is None")
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

    def serialize(self) -> et._Element:
        root = self._create_root()
        for h in self.hierarchies:
            root.append(h.serialize())
        return root

    def _create_root(self) -> et._Element:
        XSI = "http://www.w3.org/2001/XMLSchema-instance"
        nsmap = {"xsi": XSI, None: "http://www.dke.de/CAEX"}
        root = et.Element("CAEXFile", nsmap=nsmap)
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


class AMLBuilder():

    def __init__(self, god: God, configs: AspectsConfig) -> None:
        self.god = god
        self.configs = configs
        self.tree = None

    def process(self) -> None:
        file = CAEXFile("test.xml")
        # TODO may be move to CAEXfile

        # Create a lookup map of xtargets
        xtarget_lookup = {xtarget.get_guid(): InternalXTarget(
            xtarget, self.configs.levels) for xtarget in self.god.xtargets.values()}
        internal_links: list[InternalLink] = []

        # unpack connections and links
        for connection in self.god.connections.values():
            src = xtarget_lookup.get(
                connection.src.get_guid()) if connection.src else None
            dst = xtarget_lookup.get(
                connection.dest.get_guid()) if connection.dest else None
            through = xtarget_lookup.get(
                connection.through.get_guid()) if connection.through else None
            #
            for link in connection.links:
                src_pin = InternalPin(link.src_pin) if src else None
                dst_pin = InternalPin(link.dest_pin) if dst else None

                if dst_pin is not None:
                    dst.connPoints.append(dst_pin)
                if src_pin is not None:
                    src.connPoints.append(src_pin)

                if through is not None:
                    through_conn = InternalConnection(link)
                    through.connections.append(through_conn)
                    # add InternalLinks src -> through; through -> dst
                    internal_links.append(InternalLink(
                        src_pin.external, through_conn.external_a))
                    internal_links.append(InternalLink(
                        through_conn.external_b, dst_pin.external))
                else:
                    # Add InternalLink: src -> dst
                    internal_links.append(InternalLink(
                        src_pin.external, dst_pin.external))

        targets = list(xtarget_lookup.values())
        # ECAD tree InstanceHierarchy
        file.hierarchies.append(InstanceHierarchy("ECAD", "0.0.1", list(
            self.configs.levels.keys()), targets, internal_links))

        # For all aspects build trees
        aspects: dict[str, list[str]] = defaultdict(list)
        for sep, config in self.configs.levels.items():
            aspects[config.Aspect.lower()].append(sep)
        for aspect, levels in aspects.items():
            file.hierarchies.append(InstanceHierarchy(
                aspect.capitalize(), "0.0.1", levels, targets))

        # Save to file with 2-space indentation
        self.tree = et.ElementTree(file.serialize())
        # Do some error handling
        for t in targets:
            if not t.serialized:
                logger.warning(f"Target not serialized! '{t.xtarget}'")

    def output_str(self) -> str:
        # 
        if self.tree is None:
            raise ValueError("Nothing to output. Process first")
        # Serialize to string
        xml_string = et.tostring(
            self.tree,
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8"
        )
        return xml_string.decode("utf-8")
    

    def output_file(self, file_name):
        if self.tree is None:
            raise ValueError("Nothing to output. Process first")
        self.tree.write(
            file_name,
            pretty_print=True,
            xml_declaration=True,
            encoding="utf-8"
        )


if __name__ == "__main__":
    from collections import OrderedDict
    from typing import cast
    # Tests
    configs = AspectsConfig(OrderedDict([
        ('=', LevelConfig(Separator='=', Aspect='Function')),
        ('+', LevelConfig(Separator='+', Aspect='Location')),
    ]))
    tgt = XTarget(Tag("=A+B+F", configs), configs)
    for sep, val in tgt.tag.get_tag_parts().items():
        print(f"tag part {sep}{val}")

    tgt_a = XTarget(Tag("=A+B", configs), configs, attributes=[
                    SimpleAttribute("a", "tgt_a a"), SimpleAttribute("a", "tgt_a b")])
    tgt_b = XTarget(Tag("=A+C", configs), configs, attributes=[
                    SimpleAttribute("b", "tgt_b a"), SimpleAttribute("b", "tgt_b b")])
    tgt_c = XTarget(Tag("=D", configs), configs, attributes=[
                    SimpleAttribute("b", "tgt_b a"), SimpleAttribute("b", "tgt_b b")])
    links_attrs: list[list[Attribute]] = [
        [cast(Attribute, SimpleAttribute("a", "lnk a test value"))],
        [cast(Attribute, SimpleAttribute("b", "lnk b test value"))],
    ]
    conn = Connection(tgt_a, tgt_b, tgt_c)
    pin_names_a = ["A1", "A1"]
    pin_names_b = ["B1","B1"]
    links = [
        Link("lnk", conn, pa, pb, attrs) for pa, pb, attrs in zip(pin_names_a, pin_names_b, links_attrs)
    ]
    conn.links = links
    pins_a = [
        Pin(name, "src", links[0], 
            [SimpleAttribute(f"a{idx}", "A1 test value"), SimpleAttribute(f"b{idx}", "A1 test value")])
            for idx, name in enumerate(pin_names_a)
    ]
    pins_b = [
        Pin(name, "dst", links[0], 
            [SimpleAttribute(f"a{idx}", "B1 test value"), SimpleAttribute(f"b{idx}", "B1 test value")])
            for idx, name in enumerate(pin_names_b)
    ]
    
    # Tests
    item = InternalAttribute(SimpleAttribute("test", "test value")).serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalLink(
        ExternalInterface("bcda-1234", "src"),
        ExternalInterface("abcd-1234", "dst")
    ).serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalPin(pins_a[0]).serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalConnection(links[0]).serialize()
    print(et.tostring(item, pretty_print=True))

    it = InternalXTarget(tgt_a, configs.levels)
    it.set_base(InternalAspectBase(
        Aspect("+", "B"), InternalAspectBase(Aspect("=", "A"), None)))
    item = it.serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalAspect("ECAD", Aspect("=", "A1"), None).serialize()
    item1 = InternalAspect("functional", Aspect("=", "A1"), None).serialize()
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
        builder.output_file("text.aml")
