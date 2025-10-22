from collections import defaultdict
from typing import cast

from indu_doc.god import God
from indu_doc.xtarget import XTarget
from indu_doc.attributes import Attribute, SimpleAttribute
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.connection import Connection, Link, Pin
from indu_doc.tag import Tag, Aspect

from indu_doc.plugins.aml_builder.aml_abstractions import (
    InternalElementBase,
    ExternalInterface,
    InternalAttribute,
    InternalLink,
    InstanceHierarchy,
    CAEXFile,
    GUID,
    TreeNode
)

import lxml.etree as et

import logging
logger = logging.getLogger(__name__)

###################
MAIN_TREE_NAME = "ECAD"


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
            item = InternalAttribute(attr.name, str(attr)).serialize()
            root.append(item)
        # Add external interface
        root.append(self.external.serialize())
        return root


class InternalConnection(InternalElementBase):
    # do not mix with InternalLink!
    external_a: ExternalInterface
    external_b: ExternalInterface
    link: Link

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
            item = InternalAttribute(attr.name, str(attr.get_value())).serialize()
            root.append(item)

        # Add external interfaces
        root.append(self.external_a.serialize())
        root.append(self.external_b.serialize())

        return root

class InternalAspect(InternalElementBase):
    # it is also an aspect but for the selected InstanceHierarchy.
    # For ECAD it is "ECAD". This is also to make diamondID distinct from ID
    # (for DiamondID it is empty and thus consistent over trees; other Internal elements do not appear in not ECAD InstanceHierarchies)
    prefix: str  # = separator
    bmk: str     # accumulated separators and levels
    name: str    # name of current level aspect
    base: "InternalAspect | None" = None
    aspect: Aspect
    
    perspective: str
    diamondID: GUID

    def __init__(self, perspective: str, aspect: Aspect, base: "InternalAspect | None" = None):
        self.aspect = aspect
        self.name = aspect.value
        self.prefix = aspect.separator
        self.base = base
        # accumulate bmk
        self.bmk = (base.bmk if base else "") + str(aspect)
        # accumulate guid (can not use aspect GUID as it is non unique)
        self.id = self._create_guid({
            "prefix": self.prefix,
            "name": self.name,
            "base": self.base.id if self.base else ""
        })
        # set diamondId 
        self.diamondID = aspect.get_guid()
        # Update ID based on perspective (make unq across trees)
        self.perspective = perspective
        unq = {  # do not copy to reuse! - positional
            "base": self.id,
            "salt": self.perspective
        }
        self._set_guid(self._create_guid(unq))  # will override self.id and check uniqueness

    def serialize(self) -> et._Element:
        root = et.Element("InternalElement")
        root.set("Name", self.name)
        root.set("ID", self.id)

        # Add diamondID (must go first)
        item = et.SubElement(root, "SourceObjectInformation")
        item.set("OriginID", "DiamondId")
        item.set("SourceObjID", self.diamondID)

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

        # Add all atributes (if ECAD)
        if self.perspective == MAIN_TREE_NAME:
            for attr in self.aspect.attributes:
                item = InternalAttribute(attr.name, str(attr.get_value())).serialize()
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
    base: InternalAspect | None

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

    def set_base(self, base: InternalAspect):
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
            item = InternalAttribute(attr.name, str(attr.get_value())).serialize()
            root.append(item)
        # TODO IDK what are two elements called Function
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


def build_tree(name: str, levels: list[str], targets: list[InternalXTarget]) -> TreeNode:
    # form tree of objects by aspects. Level of the tree is aspect priority
    root = TreeNode()
    for t in targets:
        parts = t.xtarget.tag.get_aspects()
        # some tags do not have anything
        if not parts:
            continue
        # build tree
        current = root
        for sep in levels:
            if sep in parts:
                for aspect in parts[sep]: # composite tag (multiple instances of same sep)
                    key = str(aspect)
                    if key not in current.children:
                        # TODO or make InternalXTarget inherit InternalAspect
                        item = current.item 
                        # can be only InternalXTarget, InternalAspect or None
                        if isinstance(item, InternalXTarget):
                            item = item.base  # If it was a leaf, but some element is located even below - take base as an aspect
                        elif item and not isinstance(item, InternalAspect):
                            raise ValueError("This must not happen")
                        current.children[key] = TreeNode(
                            InternalAspect(
                                name,
                                aspect,
                                item  # type: ignore
                            )
                        )
                    current = current.children[key]

        # at the leaf, promote aspect to target (only for ECAD)
        if name == MAIN_TREE_NAME and current.item:
            if not current.item or not isinstance(current.item, InternalAspect):
                raise ValueError("This must not happen")
            t.set_base(cast(InternalAspect, current.item))
            current.item = t

    return root

class AMLBuilder():

    def __init__(self, god: God, configs: AspectsConfig) -> None:
        self.god = god
        self.configs = configs
        self.tree: et._ElementTree | None = None

    def process(self) -> None:
        # Do preprocessing:

        # Initialize a lookup map of InternalXTarget 
        xtarget_lookup = {xtarget.get_guid(): InternalXTarget(
            xtarget, self.configs.levels) for xtarget in self.god.xtargets.values()}
        internal_links: list[InternalLink] = []

        # Unpack connections and links into InternalXTarget map
        for connection in self.god.connections.values():
            src = xtarget_lookup.get(
                connection.src.get_guid()) if connection.src else None
            dst = xtarget_lookup.get(
                connection.dest.get_guid()) if connection.dest else None
            through = xtarget_lookup.get(
                connection.through.get_guid()) if connection.through else None
            #
            for link in connection.links:
                src_pin = InternalPin(link.src_pin) if link.src_pin else None
                dst_pin = InternalPin(link.dest_pin) if link.dest_pin else None

                if dst is not None and dst_pin is not None:
                    dst.connPoints.append(dst_pin)
                if src is not None and src_pin is not None:
                    src.connPoints.append(src_pin)

                if not (src_pin and dst_pin):
                    continue

                if through:
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

        # Build AML
        aml = CAEXFile("test.aml")

        # ECAD tree InstanceHierarchy
        # Can create any type of InstanceHierarchy by making your own behavior of build_tree
        ecad_tree_root = build_tree("ECAD", list(self.configs.levels.keys()), targets)
        aml.hierarchies.append(InstanceHierarchy("ECAD", "0.0.1", ecad_tree_root, internal_links))

        # For all unique aspects build trees 
        aspects: dict[str, list[str]] = defaultdict(list)
        for sep, config in self.configs.levels.items():
            aspects[config.Aspect.lower()].append(sep)
        for aspect, levels in aspects.items():
            tree_root = build_tree(aspect.capitalize(), levels, targets)
            aml.hierarchies.append(InstanceHierarchy(aspect.capitalize(), "0.0.1", tree_root))

        # Save to file with 2-space indentation
        self.tree = et.ElementTree(aml.serialize())
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
    item = InternalAttribute("test", "test value").serialize()
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
    it.set_base(InternalAspect("ECAD", Aspect("+", "B"), 
        InternalAspect("ECAD", Aspect("=", "A"), None)))
    item = it.serialize()
    print(et.tostring(item, pretty_print=True))

    item = InternalAspect("ECAD", Aspect("=", "A1"), None).serialize()
    item1 = InternalAspect("functional", Aspect("=", "A1"), None).serialize()
    print(et.tostring(item, pretty_print=True))
    print(et.tostring(item1, pretty_print=True))

    #

    # Do a fullscale test now
    from indu_doc.plugins.eplan_pdfs.page_settings import PageSettings
    from indu_doc.plugins.eplan_pdfs.eplan_pdf_plugin import EplanPDFPlugin
    from ...manager import Manager
    import logging
    logging.basicConfig(
        filename="myapp.log", encoding="utf-8", filemode="w", level=logging.INFO
    )
    ps = PageSettings.init_from_file("page_settings.json")
    cs = AspectsConfig.init_from_file("config.json")
    pdfPlugin = EplanPDFPlugin(cs, ps)
    manager: Manager = Manager(cs)
    manager.register_plugin(pdfPlugin)

    # TEST
    # from .tag import Tag
    # god = God(manager.configs)
    # god.xtargets.add(XTarget(Tag("=A+B-C", manager.configs), manager.configs, attributes=[SimpleAttribute("a", "a test value")]))
    # builder = AMLBuilder(god, manager.configs)
    # builder.process()
    # exit(0)

    #
    manager.process_files("./pdfs/sample.pdf")

    import time

    def monitor_processing(manager: Manager) -> bool:
        while True:
            states = manager.get_processing_state()
            processing = manager.is_processing()
            
            # Check if processing completed successfully or with errors
            if states:
                if not processing:
                    # Check for errors
                    has_errors = any(s['state'] == 'error' for s in states)
                    all_done = all(s['progress']['is_done'] for s in states)
                    
                    if has_errors:
                        error_messages = [s.get('error_message', 'Unknown error') 
                                        for s in states if s['state'] == 'error']
                        print(f'Processing failed: {"; ".join(error_messages)}')
                        return False
                    elif all_done:
                        print('Processing completed successfully')
                        return True
                else:
                    # Aggregate progress from all plugins
                    total_current = 0
                    total_pages = 0
                    current_files = []
                    
                    for state_info in states:
                        if state_info['state'] == 'processing':
                            progress = state_info['progress']
                            total_current += progress['current_page']
                            total_pages += progress['total_pages']
                            if progress['current_file']:
                                current_files.append(progress['current_file'])
                    
                    # Update progress text
                    if current_files:
                        # Show first file being processed
                        filename = current_files[0].split('\\')[-1]  # Get just filename
                        if len(current_files) > 1:
                            print(f"Processing: {filename} and {len(current_files)-1} more... ({total_current}/{total_pages})")
                        else:
                            print(f"Processing: {filename} ({total_current}/{total_pages})")
                    else:
                        print(f"Page {total_current} of {total_pages}")

            time.sleep(10)

    success = monitor_processing(manager)
    if success:
        print(manager.get_stats())

        builder = AMLBuilder(manager.god, manager.configs)
        builder.process()
        builder.output_file("text.aml")
