import pytest
from unittest.mock import MagicMock, patch
import lxml.etree as et
import uuid
import logging

from datetime import datetime

from indu_doc.plugins.aml_builder.aml_abstractions import (
    ISerializeable,
    InternalAttribute,
    InternalLink,
    InternalElementBase,
    ExternalInterface,
    TreeNode,
    InstanceHierarchy,
    CAEXFile,
)

# === import your actual code ===
from indu_doc.plugins.aml_builder.aml_builder import (
    InternalPin,
    InternalConnection,
    InternalAspect,
    InternalXTarget,
    AMLBuilder,
    MAIN_TREE_NAME,
    build_tree
)

class TestISerializeable:
    def test_abstract_method_call_raises(self):
        # Direct call to abstract method raises NotImplementedError
        with pytest.raises(NotImplementedError):
            ISerializeable.serialize(object())


class TestInternalAttribute:
    def test_serialize_creates_correct_xml(self):
        attr = InternalAttribute(name="Voltage", value="220V")
        el = attr.serialize()

        assert el.tag == "Attribute"
        assert el.get("Name") == "Voltage"
        assert el.get("AttributeDataType") == "xs:string"
        assert el.find("Value").text == "220V"

    def test_serialize_with_custom_type(self):
        attr = InternalAttribute(name="Speed", value="120", data_type="xs:int")
        el = attr.serialize()
        assert el.get("AttributeDataType") == "xs:int"


class DummyIE(InternalElementBase):
    def serialize(self):
        pass

class TestInternalElementBase:
    def test_create_guid_is_deterministic(self):
        base = DummyIE()
        unq = {"name": "foo", "type": "bar"}
        guid1 = base._create_guid(unq)
        guid2 = base._create_guid(unq)
        assert guid1 == guid2
        uuid.UUID(guid1)  # Valid UUID check

    def test_set_guid_adds_to_global_set_and_warns_on_duplicate(self, caplog):
        caplog.set_level(logging.WARNING)
        InternalElementBase.guids.clear()
        base1 = DummyIE()
        guid = "1234"
        base1._set_guid(guid)
        assert guid in InternalElementBase.guids

        # Trigger duplicate warning
        base2 = DummyIE()
        base2._set_guid(guid)
        assert "Non-unique ID detected" in caplog.text


class TestExternalInterface:
    def test_constructor_and_guid_generation(self):
        owner_guid = "abcd"
        iface = ExternalInterface(owner_guid, "power")
        assert iface.role == "power"
        assert iface.id == f"{owner_guid}:power"
        assert iface.id in InternalElementBase.guids

    def test_serialize_creates_correct_xml(self):
        owner_guid = "efgh"
        iface = ExternalInterface(owner_guid, "control")
        el = iface.serialize()
        assert el.tag == "ExternalInterface"
        assert el.get("Name") == "control"
        assert el.get("ID") == iface.id


class TestInternalLink:
    class DummyInterface:
        def __init__(self, id):
            self.id = id

    def test_init_and_serialize(self):
        a = self.DummyInterface("A123")
        b = self.DummyInterface("B456")
        link = InternalLink(a, b)
        assert link.refA == "A123"
        assert link.refB == "B456"
        assert link.name == "ImALink"

        el = link.serialize()
        assert el.tag == "InternalLink"
        assert el.get("RefPartnerSideA") == "A123"
        assert el.get("RefPartnerSideB") == "B456"
        assert el.get("Name") == "ImALink"


class TestTreeNode:
    def test_default_construction(self):
        node = TreeNode()
        assert node.item is None
        assert isinstance(node.children, dict)
        assert len(node.children) == 0

    def test_with_item_and_children(self):
        dummy = DummyIE()
        child = TreeNode()
        node = TreeNode(item=dummy, children={"child": child})
        assert node.item is dummy
        assert "child" in node.children
        assert isinstance(node.children["child"], TreeNode)


class DummyElement:
    """Dummy InternalElementBase-like object that supports serialize()."""
    def __init__(self, name):
        self.name = name
    def serialize(self):
        el = et.Element("InternalElement")
        el.set("Name", self.name)
        return el


class DummyLink:
    """Dummy InternalLink-like object that supports serialize()."""
    def __init__(self, name):
        self.name = name
    def serialize(self):
        el = et.Element("InternalLink")
        el.set("Name", self.name)
        return el


class TestInstanceHierarchy:
    def test_serialize_single_node_no_links(self):
        # Create tree with a single node
        root_node = TreeNode(children={
            "test_item": TreeNode(item=DummyElement("Root"))
        })
        hierarchy = InstanceHierarchy(name="TestHierarchy", version="1.0", tree=root_node)

        el = hierarchy.serialize()

        # Validate structure
        assert el.tag == "InstanceHierarchy"
        assert el.get("Name") == "TestHierarchy"
        version_el = el.find("Version")
        assert version_el is not None
        assert version_el.text == "1.0"

        # Verify that the serialized node is appended
        internals = el.findall("InternalElement")
        assert len(internals) == 1
        assert internals[0].get("Name") == "Root"

    def test_serialize_nested_tree_with_links(self):
        # Nested hierarchy
        leaf = TreeNode(item=DummyElement("Leaf"))
        mid = TreeNode(item=DummyElement("Mid"), children={"leaf": leaf})
        top = TreeNode(item=DummyElement("Top"), children={"mid": mid})
        root = TreeNode(children={"top": top})
        links = [DummyLink("L1"), DummyLink("L2")]

        hierarchy = InstanceHierarchy(name="Complex", version="2.0", tree=root, links=links)
        el = hierarchy.serialize()

        assert el.tag == "InstanceHierarchy"
        assert el.get("Name") == "Complex"
        # Confirm nested InternalElement structure
        elems = el.findall(".//InternalElement")
        names = [e.get("Name") for e in elems]
        assert names == ["Top", "Mid", "Leaf"]

        # Check links at the end
        link_elems = el.findall("InternalLink")
        assert len(link_elems) == 2
        assert {link.get("Name") for link in link_elems} == {"L1", "L2"}

    def test_serialize_raises_on_missing_item(self):
        # Create a tree where a node has None item
        child = TreeNode(item=None)
        root = TreeNode(item=DummyElement("Root"), children={"bad": child})
        hierarchy = InstanceHierarchy(name="Broken", version="1.0", tree=root)

        with pytest.raises(ValueError, match="InternlNode is None"):
            hierarchy.serialize()


class TestCAEXFile:
    def test_create_root_structure_and_namespace(self):
        c = CAEXFile("demo.aml")
        root = c._create_root()

        assert root.tag == "CAEXFile"
        assert root.get("SchemaVersion") == "3.0"
        assert root.get("FileName") == "demo.aml"

        xsi_url = "http://www.w3.org/2001/XMLSchema-instance"
        assert root.get(f"{{{xsi_url}}}schemaLocation") == \
               "http://www.dke.de/CAEX CAEX_ClassModel_V.3.0.xsd"

        # Check sub-elements
        std = root.find("SuperiorStandardVersion")
        assert std is not None and std.text == "AutomationML 2.10"

        src = root.find("SourceDocumentInformation")
        assert src is not None
        assert src.get("OriginName") == "InduDoc Transformer"
        assert src.get("OriginVersion") == "0.0.0"
        assert "github.com" in src.get("OriginURL")
        assert "T" in src.get("LastWritingDateTime")

    def test_get_datetime_returns_isoformat(self):
        c = CAEXFile("demo")
        dt_str = c._get_datetime()
        # Should be a valid ISO datetime string
        parsed = datetime.fromisoformat(dt_str)
        assert isinstance(parsed, datetime)

    def test_serialize_with_hierarchies(self, monkeypatch):
        # Patch datetime for deterministic result
        monkeypatch.setattr("indu_doc.plugins.aml_builder.aml_abstractions.CAEXFile._get_datetime", lambda self: "2025-01-01T00:00:00Z")

        # Prepare a mock hierarchy
        root_node = TreeNode(item=DummyElement("R"))
        hierarchy = InstanceHierarchy("H", "1.0", root_node)
        c = CAEXFile("file.aml")
        c.hierarchies.append(hierarchy)

        result = c.serialize()

        assert result.tag == "CAEXFile"
        assert result.find("InstanceHierarchy") is not None
        assert result.find("InstanceHierarchy").get("Name") == "H"

    def test_serialize_empty_hierarchies(self):
        c = CAEXFile("empty.aml")
        result = c.serialize()

        assert result.tag == "CAEXFile"
        assert result.find("InstanceHierarchy") is None


# === dummy support classes ===
class DummyAttr:
    def __init__(self, name, value):
        self.name = name
        self._value = value

    def __str__(self):
        return str(self._value)

    def get_value(self):
        return self._value


class DummyPin:
    def __init__(self, name, guid=None, attrs=None):
        self.name = name
        self._guid = guid or str(uuid.uuid4())
        self.attributes = attrs or []

    def get_guid(self):
        return self._guid


class DummyLLink:
    def __init__(self, name, guid=None, attrs=None):
        self.name = name
        self._guid = guid or str(uuid.uuid4())
        self.attributes = attrs or []

    def get_guid(self):
        return self._guid


class DummyAspect:
    def __init__(self, value, separator="-", guid=None, attrs=None):
        self.value = value
        self.separator = separator
        self._guid = guid or str(uuid.uuid4())
        self.attributes = attrs or []

    def __str__(self):
        return f"{self.separator}{self.value}"

    def get_guid(self):
        return self._guid


class DummyTag:
    """Provides tag.get_tag_parts()"""

    def __init__(self, parts):
        self._parts = parts

    def get_tag_parts(self):
        return self._parts


class DummyLevelConfig:
    def __init__(self, aspect_name):
        self.Aspect = aspect_name


class DummyXTarget:
    def __init__(self, name="XT1", guid=None, attrs=None, tag_parts=None):
        self.name = name
        self._guid = guid or str(uuid.uuid4())
        self.attributes = attrs or []
        self.tag = DummyTag(tag_parts or {"-": ["A", "B"], "_": ["C"]})

    def get_guid(self):
        return self._guid
    


class TestInternalPin:
    def test_constructor_and_guid_and_external(self):
        pin = DummyPin("P1")
        ip = InternalPin(pin)
        assert ip.pin is pin
        assert isinstance(ip.external, ExternalInterface)
        assert ip.id == pin.get_guid()

    def test_serialize_correct_structure(self):
        pin = DummyPin("P2", attrs=[DummyAttr("Voltage", "12V")])
        ip = InternalPin(pin)
        el = ip.serialize()
        assert el.tag == "InternalElement"
        assert el.get("ID") == ip.id
        assert el.find("Attribute").get("Name") == "Voltage"
        assert el.find("ExternalInterface").get("Name") == "ConnectionPoint"

    def test_serialize_raises_without_id(self):
        pin = DummyPin("P3")
        ip = InternalPin(pin)
        ip.id = None
        with pytest.raises(ValueError):
            ip.serialize()


class TestInternalConnection:
    def test_constructor_and_fields(self):
        link = DummyLLink("L1")
        ic = InternalConnection(link)
        assert ic.link == link
        assert isinstance(ic.external_a, ExternalInterface)
        assert isinstance(ic.external_b, ExternalInterface)
        assert ic.external_a.id.startswith(ic.id)

    def test_serialize_correct_structure(self):
        link = DummyLLink("L2", attrs=[DummyAttr("Resistance", "10 Ohm")])
        ic = InternalConnection(link)
        el = ic.serialize()
        assert el.tag == "InternalElement"
        assert el.get("Name") == f"Connection {link.name}"
        assert el.find("Attribute").get("Name") == "Resistance"
        interfaces = el.findall("ExternalInterface")
        assert len(interfaces) == 2
        assert interfaces[0].get("Name") == "SideA"
        assert interfaces[1].get("Name") == "SideB"

    def test_serialize_raises_without_id(self):
        link = DummyLLink("L3")
        ic = InternalConnection(link)
        ic.id = None
        with pytest.raises(ValueError):
            ic.serialize()


class TestInternalAspect:
    def test_constructor_and_guid_accumulation(self):
        asp = DummyAspect("A1", separator=":")
        ia = InternalAspect("Perspective1", asp)
        assert ia.aspect is asp
        assert ia.name == "A1"
        assert ":" in ia.prefix
        assert isinstance(ia.id, str)
        assert isinstance(ia.diamondID, str)
        assert ia.perspective == "Perspective1"

    def test_constructor_with_base_accumulation(self):
        base_asp = DummyAspect("Base")
        base = InternalAspect("P", base_asp)
        asp = DummyAspect("Child")
        child = InternalAspect("P", asp, base=base)
        assert base.bmk in child.bmk
        assert child.base == base

    def test_serialize_with_ecad_adds_attributes(self):
        asp = DummyAspect("ECAD", attrs=[DummyAttr("Voltage", "24V")])
        ia = InternalAspect(MAIN_TREE_NAME, asp)
        el = ia.serialize()
        assert el.tag == "InternalElement"
        assert el.get("Name") == asp.value
        assert el.find("SourceObjectInformation").get("SourceObjID") == ia.diamondID
        assert el.find("Attribute[@Name='Prefix']").find("Value").text == asp.separator
        assert el.find("Attribute[@Name='BMK']").find("Value").text == f"-{asp.value}"
        # Should include one attribute from aspect
        attr_nodes = el.findall("Attribute[@Name='Voltage']")
        assert len(attr_nodes) == 1

    def test_serialize_with_non_ecad_omits_extra_attrs(self):
        asp = DummyAspect("Mechanical", attrs=[DummyAttr("Speed", "1000rpm")])
        ia = InternalAspect("NonECAD", asp)
        el = ia.serialize()
        assert el.find("Attribute[@Name='Speed']") is None


class TestInternalXTarget:
    def test_constructor_builds_aspects_dict(self):
        xt = DummyXTarget(tag_parts={"-": ["X", "Y"], "+": ["Z"]})
        lvls = {"-": DummyLevelConfig("Mech"), "+": DummyLevelConfig("Elec")}
        x = InternalXTarget(xt, lvls)
        assert isinstance(x.aspects, dict)
        assert "mech" in x.aspects and "elec" in x.aspects
        assert all(isinstance(k, str) for k in x.aspects.keys())

    def test_serialize_raises_without_base(self):
        xt = DummyXTarget(tag_parts={"-": ["X"]})
        lvls = {"-": DummyLevelConfig("A")}
        x = InternalXTarget(xt, lvls)
        with pytest.raises(ValueError):
            x.serialize()

    def test_serialize_full_structure(self):
        xt = DummyXTarget(
            attrs=[DummyAttr("Power", "220W")],
            tag_parts={"-": ["A"], "_": ["B"]}
        )
        lvls = {"-": DummyLevelConfig("ECAD"), "_": DummyLevelConfig("Mech")}
        x = InternalXTarget(xt, lvls)

        asp = DummyAspect("Root", attrs=[DummyAttr("Voltage", "12V")])
        base = InternalAspect(MAIN_TREE_NAME, asp)
        x.set_base(base)

        # Add connection and pin
        link = DummyLLink("Lx", attrs=[DummyAttr("Resistance", "5Ω")])
        pin = DummyPin("P1", attrs=[DummyAttr("Signal", "Low")])
        x.connections.append(InternalConnection(link))
        x.connPoints.append(InternalPin(pin))

        el = x.serialize()
        assert el.tag == "InternalElement"
        assert el.get("ID") == x.id
        assert any("OrientedReferenceDesignation" in e.get("Name") for e in el.findall("Attribute"))
        assert el.find("Attribute[@Name='Power']") is not None
        # Connections and pins appended
        assert el.find("InternalElement[@Name='Connection Lx']") is not None
        assert el.find("InternalElement[@Name='ConnPoint P1']") is not None
        assert x.serialized is True


def make_xtarget_with_aspects(aspects_dict):
    xtarget = MagicMock()
    xtarget.get_guid.return_value = "guid"
    tag = MagicMock()
    tag.get_aspects.return_value = aspects_dict
    tag.get_tag_parts.return_value = {"-": ["A"]}
    xtarget.tag = tag
    xtarget.attributes = []
    return InternalXTarget(xtarget, levels={"-": MagicMock(Aspect="ECAD")})

def make_config(levels):
    cfg = MagicMock()
    cfg.levels = levels
    return cfg

def make_pin():
    pin = MagicMock()
    pin.get_guid.return_value = "pin_guid"
    pin.name = "pin"
    pin.attributes = []
    return pin

def make_link(src_pin=None, dst_pin=None):
    link = MagicMock()
    link.src_pin = src_pin
    link.dest_pin = dst_pin
    link.attributes = []
    link.get_guid.return_value = "link_guid"
    link.name = "link_name"
    return link

# ---------- Tests for build_tree ----------
class TestBuildTree:

    def test_empty_targets_returns_empty_tree(self):
        root = build_tree("ECAD", ["-"], [])
        assert isinstance(root, TreeNode)
        assert root.children == {}

    def test_skips_targets_without_aspects(self):
        xt = MagicMock()
        xt.xtarget.tag.get_aspects.return_value = {}
        root = build_tree("ECAD", ["-"], [xt])
        assert root.children == {}

    def test_builds_tree_and_promotes_main_tree(self):
        target = make_xtarget_with_aspects({"-": [DummyAspect("X")]})
        with patch("indu_doc.plugins.aml_builder.aml_builder.MAIN_TREE_NAME", "ECAD"):
            root = build_tree("ECAD", ["-"], [target])
        assert "-X" in root.children
        node = root.children["-X"]
        assert isinstance(node.item, InternalXTarget)

    def test_raises_if_item_not_aspect(self):
        target = make_xtarget_with_aspects({"-": [DummyAspect("Y")]})
        node = TreeNode()
        node.item = object()  # simulate invalid item
        node.children = {}
        with patch("indu_doc.plugins.aml_builder.aml_builder.TreeNode", return_value=node):
            with pytest.raises(ValueError, match="This must not happen"):
                build_tree("X", ["-"], [target])

# ---------- Tests for AMLBuilder ----------
class TestAMLBuilder:

    def setup_method(self):
        self.god = MagicMock()
        x1 = MagicMock()
        x1.get_guid.return_value = "GUID_1"
        x2 = MagicMock()
        x2.get_guid.return_value = "GUID_2"
        self.god.xtargets = {"1": x1, "2": x2}
        self.god.connections = {}
        self.configs = make_config({"-": MagicMock(Aspect="ECAD")})
        self.builder = AMLBuilder(self.god, self.configs)

    def test_process_creates_hierarchies_and_serializes(self, tmp_path):
        with patch("indu_doc.plugins.aml_builder.aml_builder.CAEXFile") as caex_mock, \
             patch("indu_doc.plugins.aml_builder.aml_builder.build_tree", return_value=TreeNode()):
            caex_mock.return_value.serialize.return_value = et.Element("root")
            self.builder.process()
            caex_mock.return_value.hierarchies.append.assert_called()
            assert self.builder.tree is not None

            # output_str
            xml_str = self.builder.output_str()
            assert isinstance(xml_str, str)
            assert "<" in xml_str

            # output_file
            file_path = tmp_path / "out.aml"
            self.builder.output_file(file_path)
            assert file_path.exists()
            assert "<" in file_path.read_text()

    def test_process_creates_internal_links_and_warnings(self, caplog):
        caplog.set_level(logging.WARNING)
        # setup connections with through
        src = make_xtarget_with_aspects({"-": [DummyAspect("A")]})
        dst = make_xtarget_with_aspects({"-": [DummyAspect("B")]})
        through = make_xtarget_with_aspects({"-": [DummyAspect("C")]})

        link = make_link(make_pin(), make_pin())
        conn = MagicMock()
        conn.src = src.xtarget
        conn.dest = dst.xtarget
        conn.through = through.xtarget
        conn.links = [link]
        self.god.connections = {"c": conn}
        self.god.xtargets = {x.id: x.xtarget for x in [src, dst, through]}

        with patch("indu_doc.plugins.aml_builder.aml_builder.build_tree", return_value=MagicMock()), \
             patch("indu_doc.plugins.aml_builder.aml_builder.InternalXTarget", wraps=InternalXTarget), \
             patch("indu_doc.plugins.aml_builder.aml_builder.InternalLink", wraps=InternalLink), \
             patch("indu_doc.plugins.aml_builder.aml_builder.InternalPin", wraps=InternalPin), \
             patch("indu_doc.plugins.aml_builder.aml_builder.InternalConnection", wraps=InternalConnection):
            self.builder.process()
            assert "Target not serialized!" in caplog.text

    def test_output_methods_raise_if_not_processed(self, tmp_path):
        builder = AMLBuilder(self.god, self.configs)
        with pytest.raises(ValueError):
            builder.output_str()
        with pytest.raises(ValueError):
            builder.output_file(tmp_path / "file.aml")