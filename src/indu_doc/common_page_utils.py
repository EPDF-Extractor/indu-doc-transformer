from enum import Enum
from typing import Optional
import logging

from pymupdf import pymupdf

logger = logging.getLogger(__name__)


class PageType(Enum):
    CONNECTION_LIST = "connection list"
    DEVICE_TAG_LIST = "device tag list"
    CABLE_OVERVIEW = "Cable overview"
    CABLE_DIAGRAM = "Cable diagram"
    CABLE_PLAN = "Cable plan"  # do not touch as PFD has duplicated name!
    TOPOLOGY = "Topology: Routed cables / connections"
    TERMINAL_DIAGRAM = "Terminal diagram"
    DEVICE_LIST_DE = "artikelstückliste"
    CABLE_OVERVIEW_DE = "kabelübersicht"
    CABLE_PLAN_DE = "Kabelplan"
    WIRES_PART_LIST = "Wires parts list"
    TERMINAL_DIAGRAM_DE = "Klemmenplan"


# Highlights important columns (like the ones containing tags). Other for now english. In future - internationalize
header_map_en = {
    PageType.CABLE_OVERVIEW: [
        "Cable designation",
        "Cable type",
        "Conductors",
        "ø",
        "Length",
        "Function text",
        "From",
        "To",
    ],
    PageType.CABLE_DIAGRAM: [
        "Function Text (source)",
        "Page / Column (source)",
        "src_tag",
        "src_pin",
        "Color",
        "dst_tag",
        "dst_pin",
        "Page / Column (dest)",
        "Function Text (dest)",
        "cable_tag",
    ],
    PageType.TERMINAL_DIAGRAM: [
        "strip_tag",
        "src_cable_tag",
        "Color:1",
        "Function Text",
        "src_tag",
        "src_pin",
        "strip_pin",
        "Jumpers",
        "PLC connection point",
        "dst_tag",
        "dst_pin",
        "dst_cable_tag",
        "Color:2",
        "Page / Column"
    ],
}


def detect_page_type(page: pymupdf.Page) -> Optional[PageType]:
    """Detect the type of given PDF page based on its text content.

    Args:
        page (pymupdf.Page): The PDF page to analyze.
    Returns:
        Optional[PageType]: The detected page type, or None if not identified.
    """
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" in b:  # this block contains text
            for line in b["lines"]:  # iterate through the text lines
                for s in line["spans"]:  # iterate through the text spans
                    if s["size"] > 20:  # if fontsize > 20 pt
                        for pt in PageType:
                            if pt.value.lower() == s["text"].lower():
                                logger.info(
                                    f"Page {page.number + 1} is of type {pt.name}"
                                )
                                return pt

    logger.info(f"Page {page.number + 1} type is unknown")
    return None
