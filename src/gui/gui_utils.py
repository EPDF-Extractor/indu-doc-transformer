from indu_doc.attributes import PDFLocationAttribute
from indu_doc.tag import Aspect
from indu_doc.xtarget import XTarget
import logging
logger = logging.getLogger(__name__)

def get_gui_description(target: XTarget) -> str:
    lines = []
    lines.append(f"<div class='tree-description'>")
    lines.append(
        f"<div class='target-type'><strong>Type:</strong> <span class='badge'>{target.target_type.value.upper()}</span></div>")
    lines.append(
        f"<div class='target-tag'><strong>Tag:</strong> {target.tag.tag_str}</div>")
    lines.append(
        f"<div class='target-guid'><strong>GUID:</strong> <code>{target.get_guid()}</code></div>")
    if target.attributes:
        lines.append(
            f"<div class='target-attributes'><strong>Attributes:</strong>")
        lines.append("<ul>")
        for attr in target.attributes:
            if isinstance(attr, PDFLocationAttribute):
                continue
            lines.append(f"<li>{attr}</li>")
        lines.append("</ul></div>")
    lines.append("</div>")
    return "".join(lines)

def get_aspect_gui_description(aspect: Aspect) -> str:
    lines = []
    lines.append(f"<div class='tree-description'>")
    if aspect.attributes:
        lines.append(
            f"<div class='target-attributes'><strong>Attributes:</strong>")
        lines.append("<ul>")
        for attr in aspect.attributes:
            if isinstance(attr, PDFLocationAttribute):
                continue
            lines.append(f"<li>{attr}</li>")
        lines.append("</ul></div>")
    lines.append("</div>")
    return "".join(lines)
    
# convert raw_tree to the desired format for the GUI
def convert_tree_to_gui_format(node):
    if not isinstance(node, dict):
        return []

    gui_node = []
    sorted_keys = sorted(
        # sorted by 2 keys, to have _targets last and others alphabetically
        node.keys(), key=lambda k: (k in ("_targets", "_aspects"), k))
    for key in sorted_keys:
        child = node[key]
        if key == "_targets":
            if not isinstance(child, set):
                logger.debug(
                    f"Expected set of targets, got {type(child)}")
                continue

            for target in (c for c in child if isinstance(c, XTarget)):
                gui_node.append(
                    {'id': target.tag.tag_str, 'description': get_gui_description(target), 'children': []})
        elif key == "_aspect":
            continue
        else:
            converted_children = convert_tree_to_gui_format(child)
            if "_aspect" in child:
                gui_node.append({
                    'id': str(key),
                    'description': get_aspect_gui_description(child["_aspect"]),
                    'children': converted_children or []
                })
            else:
                gui_node.append({
                    'id': str(key),
                    'children': converted_children or []
                })
    return gui_node
