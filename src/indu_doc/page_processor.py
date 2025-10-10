from __future__ import annotations

import logging

import pandas as pd
from pymupdf import pymupdf  # type: ignore

from indu_doc.attributes import AttributeType, Attribute
from indu_doc.common_page_utils import PageType, header_map_en, detect_page_type, PageInfo, PageError, ErrorType
from indu_doc.configs import default_configs
from indu_doc.footers import extract_footer
from indu_doc.god import God
from indu_doc.table_extractor import TableExtractor
from indu_doc.xtarget import XTargetType
import traceback
logger = logging.getLogger(__name__)


class PageProcessor:
    def __init__(self, god_: God):
        self.god = god_

    def run(self, page_: pymupdf.Page, page_type_: PageType):
        errors: list[PageError] = []

        # --- fetch footer ---
        footer = extract_footer(page_)
        if footer is None:
            logger.warning(f"No footer found on page {page_.number + 1} for type '{page_type_}'")
            errors.append(PageError("No footer found", error_type=ErrorType.FAULT))
            # self.god.add_errors(PageInfo(page_, None, page_type_), errors)
            return
        #
        page_info = PageInfo(page_, footer, page_type_)

        # --- fetch tables ---
        df, msgs = TableExtractor.extract(page_, page_type_)
        errors.extend(msgs)
        if df is None or df.shape[0] == 0:
            logger.warning(f"No table found on page for type '{page_type_}'")
            errors.append(PageError("No tables found", error_type=ErrorType.FAULT))
            self.god.add_errors(page_info, errors)
            return
        # 
        err = self.internationalize(df, page_type_, header_map_en)
        if err:
            errors.append(err)
        #
        self.god.add_errors(page_info, errors)

        # --- process tables ---
        self.process(df, page_info)

    @staticmethod
    def internationalize(table, page_type_: PageType, internationalization_table) -> PageError | None:
        # translate table header (for now just to english)
        if page_type_ in internationalization_table:
            new_columns = internationalization_table[page_type_]
            if len(new_columns) == table.shape[1]:
                table.columns = new_columns
            else:
                msg = f"Internationalization error: {page_type_} table shape mismatch: {len(new_columns)} vs {table.shape[1]}"
                logger.warning(msg)
                return PageError(msg, error_type=ErrorType.WARNING)
        return None

    # todo this stuff is very inefficient now, later will be grouped

    def process(self, table: pd.DataFrame, page_info: PageInfo):
        logger.info(
            f"Processing table '{page_info.page_type}' of shape {table.shape}...")
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
            PageType.STRUCTURE_IDENTIFIER_OVERVIEW: self.process_structure_identifier_overview,
            PageType.PLC_DIAGRAM: self.process_plc_diagram,
        }

        f = type_handlers.get(page_info.page_type, None)
        assert f is not None, (
            f"Specified table type '{page_info.page_type}' does not have a processor"
        )
        # concat the rest
        try:
            f(table, page_info)
        except ValueError as ve:
            self.god.create_error(page_info, f"{ve}", error_type=ErrorType.WARNING)
            logger.warning(ve.__context__)
            logger.warning(
                f"Value error processing table '{page_info.page_type}': {ve}")
        except Exception as e:
            self.god.create_error(page_info, f"{e}", error_type=ErrorType.UNKNOWN_ERROR)
            logger.warning(e.__cause__)
            logger.warning(traceback.format_exc())
            logger.warning(
                f"Unexpected error processing table '{page_info.page_type}': {e}")


    def process_connection_list(self, table: pd.DataFrame, page_info: PageInfo):
        # TODO setting
        target_1 = table.columns[1]
        target_2 = table.columns[2]
        other = [col for col in table.columns if col not in (
            target_1, target_2)]
        for idx, row in table.iterrows():
            # get primary stuff
            tag_from = str(row[target_1]).strip()
            tag_to = str(row[target_2]).strip()
            if tag_from == "" or tag_to == "":
                msg =  f"row #{idx} skipped: one/both of the connection targets are empty (is that intended?): `{tag_from}` `{tag_to}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue
            # get secondary stuff
            attributes = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )
            # build
            self.god.create_connection_with_link(
                None, tag_from, tag_to, page_info, tuple(attributes)
            )

    def process_device_tag_list(self, table: pd.DataFrame, page_info: PageInfo):
        target = table.columns[0]
        other = [col for col in table.columns if col != target]
        for idx, row in table.iterrows():
            tag = str(row[target]).strip()
            if tag == "":
                msg =  f"row #{idx} skipped: empty device tag (is that intended?): `{tag}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue
            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )

            self.god.create_xtarget(
                tag_str=tag,
                page_info=page_info,
                target_type=XTargetType.DEVICE,
                attributes=tuple(attributes)
            )

    def process_cable_overview(self, table: pd.DataFrame, page_info: PageInfo):
        target = table.columns[0]
        target_from = table.columns[-1]
        target_to = table.columns[-2]
        other = [
            col for col in table.columns if col not in (target, target_from, target_to)
        ]
        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tag_from = str(row[target_from]).strip()
            tag_to = str(row[target_to]).strip()
            if tag == "" or (tag_from == "" and tag_to == ""):
                msg = f"row #{idx} skipped: empty cable tag (is that intended?): `{tag}` from=`{tag_from}` to=`{tag_to}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue
            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )
            # create connections if from/to specified
            if tag_from and tag_to:
                self.god.create_connection(
                    tag, tag_from, tag_to, page_info, tuple(
                        attributes)
                )

    def process_cable_plan(self, table: pd.DataFrame, page_info: PageInfo):
        target = table.columns[-3]
        target_src = table.columns[1]
        target_dst = table.columns[-5]
        other = [
            col for col in table.columns if col not in (target, target_src, target_dst)
        ]
        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tag_src = str(row[target_src]).strip()
            tag_dst = str(row[target_dst]).strip()
            if tag == "" or tag_src == "" or tag_dst == "":
                msg = f"row #{idx} skipped: empty cable connection info (is that intended?): `{tag}` from=`{tag_src}` to=`{tag_dst}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue
            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )
            # build
            self.god.create_connection_with_link(
                tag, tag_src, tag_dst, page_info, tuple(attributes)
            )

    def process_topology(self, table: pd.DataFrame, page_info: PageInfo):
        target = table.columns[0]
        target_src = table.columns[4]
        target_dst = table.columns[7]
        target_route = table.columns[6]
        other = [
            col
            for col in table.columns
            if col not in (target, target_src, target_dst, target_route)
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            tags_src = str(row[target_src]).strip()
            tags_dst = str(row[target_dst]).strip()
            tags_route = str(row[target_route]).strip()

            if tag == "" or tags_src == "" or tags_dst == "" or tags_route == "":
                msg = f"row #{idx} skipped: empty topology tag (is that intended?): `{tag}` from=`{tags_src}` to=`{tags_dst}` route=`{tags_route}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue

            # get secondary stuff
            attributes = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )

            # Add route as attribute
            attributes.append(
                self.god.create_attribute(
                    AttributeType.ROUTING_TRACKS, "route", tags_route)
            )

            # build connections for all combinations of src and dst tags
            from itertools import product

            for t1, t2 in product(tags_src.split(";"), tags_dst.split(";")):
                self.god.create_connection(
                    tag, t1, t2, page_info, tuple(attributes)
                )

    def process_wires_part_list(self, table: pd.DataFrame, page_info: PageInfo):
        target_src = table.columns[0]
        target_dst = table.columns[1]
        target_route = table.columns[-1]  # TODO as attribute
        other = [
            col
            for col in table.columns
            if col not in (target_src, target_dst, target_route)
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag_src = str(row[target_src]).strip()
            tag_dst = str(row[target_dst]).strip()
            tags_route = str(row[target_route]).strip()

            if tag_src == "" or tag_dst == "":
                msg = f"row #{idx} skipped: empty wire connection info (is that intended?): from=`{tag_src}` to=`{tag_dst}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue

            # get secondary stuff
            attributes = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )

            # Add route as attribute
            if tags_route != "":
                attributes.append(
                    self.god.create_attribute(
                        AttributeType.ROUTING_TRACKS, "route", tags_route)
                )

            # build
            self.god.create_connection_with_link(
                None, tag_src, tag_dst, page_info, tuple(
                    attributes)
            )

    def process_cable_diagram(self, table: pd.DataFrame, page_info: PageInfo):
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

        for idx, row in table.iterrows():
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
                msg = f"row #{idx} skipped: empty cable diagram info (is that intended?): `{tag}` from=`{tag_src}``{pin_src}` to=`{tag_dst}``{pin_dst}` "
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue

            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )

            # build (TODO HOW TO TREAT PINS SEPARATELY)
            # build connections for all combinations of src and dst tags
            from itertools import product

            # Split and zip source/destination pairs
            src_pairs = list(zip(tag_src.split(";"), pin_src.split(";"), tag.split(";")))
            dst_pairs = list(zip(tag_dst.split(";"), pin_dst.split(";")))

            for (tag_s, pin_s, tag_), (tag_d, pin_d) in product(src_pairs, dst_pairs):
                self.god.create_connection_with_link(
                    tag_,
                    tag_s + ":" + pin_s,
                    tag_d + ":" + pin_d,
                    page_info,
                    tuple(attributes)
                )


    def process_plc_diagram(self, table: pd.DataFrame, page_info: PageInfo):
        target = table.columns[0]
        address = table.columns[1]
        other = [
            col
            for col in table.columns
            if col
            not in (target, address)
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()
            plc_addr = str(row[address]).strip()

            if tag == "" or plc_addr == "":
                msg = f"row #{idx} skipped: empty PLC diagram info (is that intended?): `{tag}` addr=`{plc_addr}`"
                self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
                logger.warning(msg)
                continue

            # get secondary stuff
            meta: dict[str, str] = {}
            for name in other:
                value = str(row[name]).strip()
                if name and value:
                    meta[name] = value

            # create attribute
            attr = self.god.create_attribute(
                AttributeType.PLC_ADDRESS, plc_addr, meta)

            # add attribute to xtarget with tag
            self.god.create_xtarget(tag, page_info, XTargetType.DEVICE, (attr,))


    def process_structure_identifier_overview(self, table: pd.DataFrame, page_info: PageInfo):
        target = table.columns[0]
        other = [
            col
            for col in table.columns
            if col != target
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row[target]).strip()

            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )

            # create aspect
            self.god.create_aspect(tag, page_info, tuple(attributes))


    def process_terminal_diagram(self, table: pd.DataFrame, page_info: PageInfo):
        # this table has to be treated as 2 tables
        # TODO awful double mapping
        self.process_cable_diagram(
            table.iloc[:, [2, 3, 4, 5, 8, 0, 6, 13, 1]], page_info)
        self.process_cable_diagram(
            table.iloc[:, [12, 3, 0, 6, 8, 9, 10, 13, 11]], page_info)


if __name__ == "__main__":
    doc = pymupdf.open("pdfs/sample.pdf")
    god = God(configs=default_configs)
    processor = PageProcessor(god)

    page = doc.load_page(211)  # Load the first page
    page_type = detect_page_type(page)
    if page_type is not None:
        processor.run(page, page_type)
    else:
        logger.warning(
            # type: ignore
            f"Could not detect page type for page #{page.number + 1}")
    print(god)
    for id, tgt in god.xtargets.items():
        print(tgt)
        print(tgt.tag.get_aspects())
        print(tgt.attributes)

    for id, a in god.aspects.items():
        print(a)
