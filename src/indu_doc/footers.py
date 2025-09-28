from typing import Optional

import pymupdf
from enum import Enum
from dataclasses import dataclass

import logging

logger = logging.getLogger(__name__)


class PaperSize(Enum):
    A1_HORIZONTAL = "A1_horizontal"
    A3_HORIZONTAL = "A3_horizontal"
    A4 = "A4"


@dataclass
class PageFooter:
    project_name: str
    product_name: str
    tags: list[str]  # list of the tag strings found in the footer

    def __hash__(self) -> int:
        return hash((self.project_name, self.product_name, tuple(self.tags)))

    def __eq__(self, other) -> bool:
        if not isinstance(other, PageFooter):
            return False
        return (
            self.project_name == other.project_name
            and self.product_name == other.product_name
            and self.tags == other.tags
        )


def get_paper_size(page: pymupdf.Page) -> PaperSize:
    """
    Determine the paper type based on the page dimensions.
    Args:
        page: The PyMuPDF page object
    Returns:
        PaperType: The paper type enum value (A4, A1_horizontal, A3_horizontal)
    """

    def compare_with_eps(v1, v2, eps=5):
        """Compare two values with a small epsilon to account for floating point precision."""
        return abs(v1 - v2) < eps

    page_h, page_w = page.rect.height, page.rect.width

    # Define paper dimensions in points (1 point = 1/72 inch)
    paper_dimensions = {
        PaperSize.A4: (595.78, 842.39),  # A4 size in points
        # A1 horizontal size in points
        PaperSize.A1_HORIZONTAL: (2384.44, 1684.28),
        # A3 horizontal size in points
        PaperSize.A3_HORIZONTAL: (1191, 1683.78),
    }

    for paper_type, (width, height) in paper_dimensions.items():
        if (compare_with_eps(page_w, width) and compare_with_eps(page_h, height)) or (
            compare_with_eps(page_w, height) and compare_with_eps(page_h, width)
        ):
            return paper_type
    return PaperSize.A3_HORIZONTAL  # Default to A3 horizontal if no match found


def get_footer_coordinates(page: pymupdf.Page, verbose: bool = False) -> dict:
    """
    Get the coordinates for footer elements based on paper type.

    Args:
        page: The PyMuPDF page object

    Returns:
        dict: Dictionary containing coordinates for each footer element
    """
    page_h, page_w = page.rect.height, page.rect.width

    # Define coordinates for different paper types
    paper_configs = {
        PaperSize.A4: {
            "project_name": (226.64, 796.97, 323.20, 808.31),
            "product_name": (),
            # top-left of table
            "table_start": (page_w - 3 * 102.25, page_h - 5 * 11.4),
            # bottom-right corner minus a Format A4 footer
            "table_end": (page_w, page_h - 11.4),
            "cell_size": (102.25, 11.4),  # (width, height)
        },
        PaperSize.A1_HORIZONTAL: {
            "project_name": (1757.66, 1514.16, 2029.39, 1559.34),
            "product_name": (1757.06, 1667.31, 1904.72, 1683.53),
            "table_start": (2029.63, 1616.15),
            "table_end": (2261.94, 1650.09),
            "cell_size": (120, 34.16),
        },
        PaperSize.A3_HORIZONTAL: {
            "project_name": (170, 797, 397, 831),
            "product_name": (702, 797, 885, 831),
            "table_start": (page_w - 3 * 102.25, page_h - 4 * 11.4),
            "table_end": (page_w, page_h),
            "cell_size": (102.25, 11.4),
        },
    }
    # Determine the paper type from the page dimensions
    paper_type = get_paper_size(page)
    if paper_type not in paper_configs:
        paper_type = PaperSize.A3_HORIZONTAL  # default to A3 horizontal

    config = paper_configs[paper_type]
    if verbose:
        logger.info(f"Using paper type: {paper_type.value}")

    # Calculate table cell coordinates
    cell_width, cell_height = config["cell_size"]

    # calculate how many cells we have
    table_coords: list[list[tuple[float, float, float, float]]] = []

    num_rows = round((page_h - config["table_start"][1]) / cell_height)
    num_cols = round((page_w - config["table_start"][0]) / cell_width)
    start_x = config["table_start"][0]
    start_y = config["table_start"][1]

    for i in range(num_rows):  # rows
        row_coords = []
        for j in range(num_cols):  # columns
            x1: float = start_x + j * cell_width
            y1: float = start_y + i * cell_height
            x2: float = x1 + cell_width
            y2: float = y1 + cell_height
            row_coords.append((x1, y1, x2, y2))
        table_coords.append(row_coords)

    return {
        "project_name": config["project_name"],
        "product_name": config["product_name"],
        "table_cells": table_coords,
        "table_info": {
            "start_point": config["table_start"],
            "end_point": config["table_end"],
            "cell_size": config["cell_size"],
        },
    }


def extract_text_from_rect(page: pymupdf.Page, coords: tuple) -> str:
    """Extract text from a rectangle defined by coordinates."""
    return page.get_text("text", clip=pymupdf.Rect(*coords), sort=True).strip()  # type: ignore


def extract_footer(page: pymupdf.Page, verbose: bool = False) -> Optional[PageFooter]:
    """
    Extract footer information from a page, supporting different paper types.

    Args:
        page: The PyMuPDF page object
        paper_type: The paper type (PaperType enum)
        verbose: Whether to print debug information

    Returns:
        dict: A dictionary with keys "project_name", "product_name", and "footer_table" containing the extracted data.
        footer_table: A 2D list of table cells with their text content.
        Returns None if essential elements are not found.
    """
    # Get coordinates for the specified paper type
    coords = get_footer_coordinates(page, verbose)

    if not (page.rect and (page.number is not None)):
        logger.warning(f"Page rect or number not found in page")
        return None
    page_h, page_w = page.rect.height, page.rect.width
    if verbose:
        logger.info(f"Page size: {page_w} x {page_h}")

    # Extract project name
    projectName = extract_text_from_rect(page, coords["project_name"])
    if not projectName:
        logger.warning(
            f"projectName not found in page: {page.number + 1}, The page most probably has no footer, returning None to be safe"
        )
        return None

    if verbose:
        logger.info(f"Found projectName: {projectName}")

    # Extract full path
    product_name = extract_text_from_rect(page, coords["product_name"])
    if not product_name:
        logger.warning(f"product_name not found in page: {page.number + 1}")

    if verbose:
        logger.info(f"Found product_name: {product_name}")

    # Extract table cells
    num_rows = len(coords["table_cells"])
    num_cols = len(coords["table_cells"][0]) if coords["table_cells"] else 0

    if verbose:
        logger.info(f"Table cells: {num_rows} rows, {num_cols} columns")
    if num_rows == 0 or num_cols == 0:
        logger.warning(f"No table cells found in page: {page.number + 1}")

    cells = []
    for i in range(num_rows):
        row = []
        for j in range(num_cols):
            cell_coords = coords["table_cells"][i][j]
            cell_text = extract_text_from_rect(page, cell_coords)
            row.append(cell_text)
        cells.append(row)

    if verbose:
        logger.info("Extracted footer table cells:")
        for i, row in enumerate(cells):
            logger.info(f"Row {i}: {row}")

    def get_hierarchy_from_footer(tab: list) -> list:
        needed = [tab[0][0], tab[2][0], tab[0][1], tab[2][1], tab[0][2]]
        # Return only non-empty elements
        return [elem for elem in needed if elem]

    return PageFooter(
        project_name=projectName,
        product_name=product_name,
        tags=get_hierarchy_from_footer(cells),
    )
