from dataclasses import dataclass
from enum import Enum
import os
from typing import Optional
import logging

from pymupdf import pymupdf  # type: ignore

from indu_doc.footers import PageFooter

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    FAULT = "FAULT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class PageError:
    message: str
    error_type: ErrorType = ErrorType.UNKNOWN_ERROR

    def __hash__(self):
        return hash((self.message, self.error_type))


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
    STRUCTURE_IDENTIFIER_OVERVIEW = "Structure identifier overview"
    PLC_DIAGRAM = "PLC diagram"


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
    blocks = page.get_text("dict")["blocks"] # type: ignore
    for b in blocks:
        if "lines" in b:  # this block contains text
            for line in b["lines"]:  # iterate through the text lines
                for s in line["spans"]:  # iterate through the text spans
                    if s["size"] > 20 and s["size"] < 30:  # if fontsize > 20 pt and < 30 pt
                        for pt in PageType:
                            if pt.value.strip().lower() == s["text"].strip().lower():
                                logger.debug(
                                    f"Page {page.number + 1} is of type {pt.name}" # type: ignore
                                )
                                return pt

    logger.debug(f"Page {page.number + 1} type is unknown") # type: ignore
    return None


@dataclass
class PageInfo:
    page: pymupdf.Page
    page_footer: PageFooter
    page_type: PageType

    def __hash__(self) -> int:
        return hash((self.page, self.page_footer, self.page_type))
