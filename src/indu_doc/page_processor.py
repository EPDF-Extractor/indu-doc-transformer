from __future__ import annotations

import logging

import pandas as pd
from pymupdf import pymupdf

from .attributes import AttributeType, Attribute
from .common_page_utils import PageType, header_map_en, detect_page_type
from .configs import default_configs
from .footers import extract_footer, PageFooter
from .god import God
from .table_extractor import TableExtractor
from .xtarget import XTargetType

logger = logging.getLogger(__name__)


class PageProcessor:
    def __init__(self, god_: God):
        self.god = god_

    def run(self, page_: pymupdf.Page, page_type_: PageType):
        df = TableExtractor.extract(page_, page_type_)
        if df is None or df.shape[0] == 0:
            logger.warning(f"No table found on page for type '{page_type_}'")
            return
        self.internationalize(df, page_type_, header_map_en)

        footer = extract_footer(page_)
        if footer is None:
            logger.warning(
                f"No footer found on page {page_.number + 1} for type '{page_type_}'"
            )
            return

        # 4. process tables (using tables & footers TODO)
        self.process(df, footer, page_type_)

    @staticmethod
    def internationalize(table, page_type_: PageType, internationalization_table):
        # translate table header (for now just to english)
        if page_type_ in internationalization_table:
            new_columns = internationalization_table[page_type_]
            if len(new_columns) == table.shape[1]:
                table.columns = new_columns
            else:
                print(
                    f"Internationalization error: {page_type_} table shape mismatch: {len(new_columns)} vs {table.shape[1]}"
                )

    # todo this stuff is very inefficient now, later will be grouped

    def process(self, table: pd.DataFrame, footer: PageFooter, page_type_: PageType):
        logger.info(f"Processing table '{page_type_}' of shape {table.shape}...")
        if table.shape[0] == 0:
            return

        type_handlers = {
            PageType.CONNECTION_LIST: self.process_connection_list,
            PageType.DEVICE_TAG_LIST: self.process_device_tag_list,
            PageType.DEVICE_LIST_DE: self.process_device_tag_list,
            PageType.CABLE_OVERVIEW: self.process_cable_overview,
            PageType.CABLE_PLAN: self.process_cable_plan,
            PageType.TOPOLOGY: self.process_topology,
            PageType.WIRES_PART_LIST: self.process_wires_part_list,
            PageType.TERMINAL_DIAGRAM: self.process_terminal_diagram,
            PageType.CABLE_DIAGRAM: self.process_cable_diagram,
        }

        f = type_handlers.get(page_type_, None)
        assert f is not None, (
            f"Specified table type '{page_type_}' does not have a processor"
        )
        # concat the rest
        try:
            f(table, footer)
        except ValueError as ve:
            logger.warning(f"ValueError processing table '{page_type_}': {ve}")
        except Exception as e:
            logger.warning(f"Unexpected error processing table '{page_type_}': {e}")
        return

    def process_connection_list(self, table, footer: PageFooter):
        # TODO setting
        target_1 = table.columns[1]
        target_2 = table.columns[2]
        other = [col for col in table.columns if col not in (target_1, target_2)]
        for _, row in table.iterrows():
            # get primary stuff
            tag_from = str(row[target_1]).strip()
            tag_to = str(row[target_2]).strip()
            if tag_from == "" or tag_to == "":
                logger.warning(
                    f"one of the connection targets are empty (is that intended?): {tag_from} {tag_to}"
                )
                continue
            # get secondary stuff
            attributes = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )
            # build
            self.god.create_connection_with_link(
                None, tag_from, tag_to, tuple(attributes), footer
            )

    def process_device_tag_list(self, table, footer: PageFooter):
        target = table.columns[0]
        other = [col for col in table.columns if col != target]
        for _, row in table.iterrows():
            tag = str(row[target]).strip()
            if tag == "":
                logger.warning(f"empty device tag (is that intended?): {tag}")
                continue
            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )

            self.god.create_xtarget(
                tag_str=tag,
                target_type=XTargetType.DEVICE,
                footer=footer,
                attributes=tuple(attributes),
            )

    def process_cable_overview(self, table, footer: PageFooter):
        target = table.columns[0]
        target_from = table.columns[-1]
        target_to = table.columns[-2]
        other = [
            col for col in table.columns if col not in (target, target_from, target_to)
        ]
        for _, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tag_from = str(row[target_from]).strip()
            tag_to = str(row[target_to]).strip()
            if tag == "" or (tag_from == "" and tag_to == ""):
                logger.warning(
                    f"empty cable tag (is that intended?): {tag} {tag_from} {tag_to}"
                )
                continue
            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )
            # create connections if from/to specified
            if tag_from and tag_to:
                self.god.create_connection(
                    tag, tag_from, tag_to, tuple(attributes), footer
                )

    def process_cable_plan(self, table, footer: PageFooter):
        target = table.columns[-3]
        target_src = table.columns[1]
        target_dst = table.columns[-5]
        other = [
            col for col in table.columns if col not in (target, target_src, target_dst)
        ]
        for _, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tag_src = str(row[target_src]).strip()
            tag_dst = str(row[target_dst]).strip()
            if tag == "" or tag_src == "" or tag_dst == "":
                logger.warning(
                    f"empty cable connection info (is that intended?): {tag} {tag_src} {tag_dst}"
                )
                continue
            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )
            # build
            self.god.create_connection_with_link(tag, tag_src, tag_dst, tuple(attributes), footer)

    def process_topology(self, table, footer: PageFooter):
        target = table.columns[0]
        target_src = table.columns[4]
        target_dst = table.columns[7]
        target_route = table.columns[6]
        other = [
            col
            for col in table.columns
            if col not in (target, target_src, target_dst, target_route)
        ]

        for _, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tags_src = str(row[target_src]).strip()
            tags_dst = str(row[target_dst]).strip()
            tags_route = str(row[target_route]).strip()

            if tag == "" or tags_src == "" or tags_dst == "" or tags_route == "":
                logger.warning(
                    f"empty topology tag (is that intended?): {tag} {tags_src} {tags_dst} {tags_route}"
                )
                continue

            # get secondary stuff
            attributes = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )

            # Add route as attribute
            attributes.append(
                self.god.create_attribute(AttributeType.SIMPLE, "route", tags_route)
            )

            # build connections for all combinations of src and dst tags
            from itertools import product

            for t1, t2 in product(tags_src.split(";"), tags_dst.split(";")):
                self.god.create_connection(tag, t1, t2, tuple(attributes), footer)

    def process_wires_part_list(self, table, footer: PageFooter):
        target_src = table.columns[0]
        target_dst = table.columns[1]
        target_route = table.columns[-1]  # TODO as attribute
        other = [
            col
            for col in table.columns
            if col not in (target_src, target_dst, target_route)
        ]

        for _, row in table.iterrows():
            # get primary stuff
            tag_src = str(row[target_src]).strip()
            tag_dst = str(row[target_dst]).strip()
            tags_route = str(row[target_route]).strip()

            if tag_src == "" or tag_dst == "":
                logger.warning(
                    f"empty wire connection info (is that intended?): {tag_src} {tag_dst}"
                )
                continue

            # get secondary stuff
            attributes = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )

            # Add route as attribute
            if tags_route != "":
                attributes.append(
                    self.god.create_attribute(AttributeType.SIMPLE, "route", tags_route)
                )

            # build
            self.god.create_connection_with_link(
                None, tag_src, tag_dst, tuple(attributes), footer
            )

    def process_cable_diagram(self, table, footer: PageFooter):
        target = table.columns[-1]
        target_src = table.columns[2]
        target_dst = table.columns[5]
        target_src_pin = table.columns[3]
        target_dst_pin = table.columns[6]
        other = [
            col
            for col in table.columns
            if col
            not in (target, target_src, target_dst, target_src_pin, target_dst_pin)
        ]

        for _, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tag_src = str(row[target_src]).strip()
            tag_dst = str(row[target_dst]).strip()
            pin_src = str(row[target_src_pin]).strip()
            pin_dst = str(row[target_dst_pin]).strip()

            if (
                tag_src == ""
                and tag_dst == ""
                and pin_src == ""
                and pin_dst == ""
            ):
                logger.warning(
                    f"empty cable diagram info (is that intended?): {tag} {tag_src} {tag_dst} {pin_src} {pin_dst}"
                )
                continue

            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(AttributeType.SIMPLE, name, value)
                    )

            # build (TODO HOW TO TREAT PINS SEPARATELY)
            self.god.create_connection_with_link(
                tag,
                tag_src + ":" + pin_src,
                tag_dst + ":" + pin_dst,
                tuple(attributes),
                footer,
            )

    def process_terminal_diagram(self, table, footer: PageFooter):
        # this table has to be treated as 2 tables
        # TODO awful double mapping
        self.process_cable_diagram(table.iloc[:, [2, 3, 4, 5, 8, 0, 6, 13, 1]], footer)
        self.process_cable_diagram(table.iloc[:, [12, 3, 0, 6, 8, 9, 10, 13, 11]], footer)


if __name__ == "__main__":
    doc = pymupdf.open("pdfs/sample.pdf")
    god = God(configs=default_configs)
    processor = PageProcessor(god)

    page = doc.load_page(140)  # Load the first page
    page_type = detect_page_type(page)
    if page_type is not None:
        processor.run(page, page_type)
    else:
        logger.warning(f"Could not detect page type for page #{page.number + 1}")
    print(god)


if __name__ == "__main__":
    doc = pymupdf.open("pdfs/sample.pdf")
    god = God(configs=default_configs)
    processor = PageProcessor(god)

    page = doc.load_page(140)  # Load the first page
    page_type = detect_page_type(page)
    if page_type is not None:
        processor.run(page, page_type)
    else:
        logger.warning(f"Could not detect page type for page #{page.number + 1}")
    print(god)
