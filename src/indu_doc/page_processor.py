from __future__ import annotations

import logging

import pandas as pd
from pymupdf import pymupdf  # type: ignore

from indu_doc.attributes import AttributeType, Attribute
from indu_doc.common_page_utils import PageType, detect_page_type, PageInfo, PageError, ErrorType
from indu_doc.page_settings import PageSettings
from indu_doc.configs import default_configs
from indu_doc.footers import extract_footer
from indu_doc.god import God
from indu_doc.table_extractor import TableExtractor
from indu_doc.xtarget import XTargetType
import traceback
logger = logging.getLogger(__name__)


class PageProcessor:
    def __init__(self, god_: God, settings: PageSettings):
        self.god = god_
        self.settings = settings
        self.type_map = self.settings.to_enum() # gives appropriate page name mapping

    def run(self, page_: pymupdf.Page):
        errors: list[PageError] = []

        # --- detect page type ---
        page_type_ = detect_page_type(page_, self.type_map)
        if not page_type_:
            logger.warning(f"Could not detect page type for page #{page_.number + 1}")
            errors.append(PageError("Could not detect page type", error_type=ErrorType.FAULT))
            return
    
        # --- get setup ---
        if page_type_ not in self.settings:
            assert "Must not happen"
        setup = self.settings[page_type_]

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
        df, msgs = TableExtractor.extract(page_, page_type_, setup)
        errors.extend(msgs)
        if df is None or df.shape[0] == 0:
            logger.warning(f"No table found on page for type '{page_type_}'")
            errors.append(PageError("No tables found", error_type=ErrorType.FAULT))
            self.god.add_errors(page_info, errors)
            return
        #
        self.god.add_errors(page_info, errors)

        # --- process tables ---
        self.process(df, page_info)

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
            # PageType.CABLE_PLAN: self.process_cable_plan,
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
            logger.debug(traceback.format_exc())
            logger.warning(
                f"Unexpected error processing table '{page_info.page_type}': {e}")


    def process_connection_list(self, table: pd.DataFrame, page_info: PageInfo):
        # TODO setting
        other = [col for col in table.columns if col not in (
            "src_pin_tag", "dst_pin_tag", "name")
            and not col.startswith("_")
        ]
        for idx, row in table.iterrows():
            # get primary stuff
            tag_from = str(row["src_pin_tag"]).strip()
            tag_to = str(row["dst_pin_tag"]).strip()
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
            # get meta stuff
            loc = None
            if "_loc" in row:
                loc = self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                attributes.append(loc)
            # build
            self.god.create_connection_with_link(
                None, tag_from, tag_to, page_info, tuple(attributes), loc
            )

    def process_device_tag_list(self, table: pd.DataFrame, page_info: PageInfo):
        other = [col for col in table.columns 
            if col != "tag"
            and not col.startswith("_") 
        ]
        for idx, row in table.iterrows():
            tag = str(row["tag"]).strip()
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
            
            # get meta stuff
            if "_loc" in row:
                attributes.append(
                    self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                )

            self.god.create_xtarget(
                tag_str=tag,
                page_info=page_info,
                target_type=XTargetType.DEVICE,
                attributes=tuple(attributes)
            )

    def process_cable_overview(self, table: pd.DataFrame, page_info: PageInfo):
        other = [
            col for col in table.columns if col not in ("cable_tag", "src_tag", "dst_tag")
            and not col.startswith("_")
        ]
        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row["cable_tag"]).strip()
            tag_from = str(row["src_tag"]).strip()
            tag_to = str(row["dst_tag"]).strip()
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
            # get meta stuff
            loc = None
            if "_loc" in row:
                loc = self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                attributes.append(loc)
            # create connections if from/to specified
            if tag_from and tag_to:
                self.god.create_connection(
                    tag, tag_from, tag_to, page_info, tuple(
                        attributes), loc
                )

    # TODO outdated can not test
    # def process_cable_plan(self, table: pd.DataFrame, page_info: PageInfo):
    #     target = table.columns[-3]
    #     target_src = table.columns[1]
    #     target_dst = table.columns[-5]
    #     other = [
    #         col for col in table.columns if col not in (target, target_src, target_dst)
    #         and not col.startswith("_")
    #     ]
    #     for idx, row in table.iterrows():
    #         # get primary stuff
    #         tag = str(row[target]).strip()
    #         tag_src = str(row[target_src]).strip()
    #         tag_dst = str(row[target_dst]).strip()
    #         if tag == "" or tag_src == "" or tag_dst == "":
    #             msg = f"row #{idx} skipped: empty cable connection info (is that intended?): `{tag}` from=`{tag_src}` to=`{tag_dst}`"
    #             self.god.create_error(page_info, msg, error_type=ErrorType.WARNING)
    #             logger.warning(msg)
    #             continue
    #         # get secondary stuff
    #         attributes: list[Attribute] = []
    #         for name in other:
    #             value = str(row[name]).strip()
    #             if name != "" and value != "":
    #                 attributes.append(
    #                     self.god.create_attribute(
    #                         AttributeType.SIMPLE, name, value)
    #                 )
    #         # get meta stuff
    #         if "_loc" in row:
    #             attributes.append(
    #                 self.god.create_attribute(
    #                     AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
    #             )
    #         # build
    #         self.god.create_connection_with_link(
    #             tag, tag_src, tag_dst, page_info, tuple(attributes)
    #         )

    def process_topology(self, table: pd.DataFrame, page_info: PageInfo):
        other = [
            col
            for col in table.columns
            if col not in ("designation", "src_tags", "dst_tags", "route")
            and not col.startswith("_")
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row["designation"]).strip()
            tags_src = str(row["src_tags"]).strip()
            tags_dst = str(row["dst_tags"]).strip()
            tags_route = str(row["route"]).strip()

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

            # get meta stuff
            loc = None
            if "_loc" in row:
                loc = self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                attributes.append(loc)

            # Add route as attribute
            attributes.append(
                self.god.create_attribute(
                    AttributeType.ROUTING_TRACKS, "route", tags_route)
            )

            # build connections for all combinations of src and dst tags
            from itertools import product

            for t1, t2 in product(tags_src.split(";"), tags_dst.split(";")):
                self.god.create_connection(
                    tag, t1, t2, page_info, tuple(attributes), loc
                )

    def process_wires_part_list(self, table: pd.DataFrame, page_info: PageInfo):
        other = [
            col
            for col in table.columns
            if col not in ("src_pin_tag", "dst_pin_tag", "route")
            and not col.startswith("_")
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag_src = str(row["src_pin_tag"]).strip()
            tag_dst = str(row["dst_pin_tag"]).strip()
            tags_route = str(row["route"]).strip()

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

            # get meta stuff
            loc = None
            if "_loc" in row:
                loc = self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                attributes.append(loc)

            # Add route as attribute
            if tags_route != "":
                attributes.append(
                    self.god.create_attribute(
                        AttributeType.ROUTING_TRACKS, "route", tags_route)
                )

            # build
            self.god.create_connection_with_link(
                None, tag_src, tag_dst, page_info, tuple(
                    attributes), loc
            )

    def process_cable_diagram(self, table: pd.DataFrame, page_info: PageInfo):
        other = [
            col
            for col in table.columns
            if col
            not in ("cable_tag", "src_tag", "src_pin", "dst_tag", "dst_pin") 
            and not col.startswith("_")
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row["cable_tag"]).strip()
            tag_src = str(row["src_tag"]).strip()
            tag_dst = str(row["dst_tag"]).strip()
            pin_src = str(row["src_pin"]).strip()
            pin_dst = str(row["dst_pin"]).strip()

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

            # get meta stuff
            loc = None
            if "_loc" in row:
                loc = self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                attributes.append(loc)
                # TODO for now I ignore it - might not have it
                # cable_loc = self.god.create_attribute(
                #         AttributeType.PDF_LOCATION, "location", row["_loc_cable"])    
                # conn_loc = self.god.create_attribute(
                #         AttributeType.PDF_LOCATION, "location", row["_loc_conn"])             

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
                    tuple(attributes),
                    loc
                )


    def process_plc_diagram(self, table: pd.DataFrame, page_info: PageInfo):
        other = [
            col
            for col in table.columns
            if col
            not in ("tag", "plc_addr")
            and not col.startswith("_")
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row["tag"]).strip()
            plc_addr = str(row["plc_addr"]).strip()

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

            attributes: list[Attribute] = []
            # create attribute
            attributes.append( 
                self.god.create_attribute(
                    AttributeType.PLC_ADDRESS, plc_addr, meta)
            )
            
            # get meta stuff
            if "_loc" in row:
                attributes.append(
                    self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                )

            # add attribute to xtarget with tag
            self.god.create_xtarget(tag, page_info, XTargetType.DEVICE, tuple(attributes))


    def process_structure_identifier_overview(self, table: pd.DataFrame, page_info: PageInfo):
        other = [
            col
            for col in table.columns
            if col != "tag"
            and not col.startswith("_")
        ]

        for idx, row in table.iterrows():
            # get primary stuff
            tag = str(row["tag"]).strip()

            # get secondary stuff
            attributes: list[Attribute] = []
            for name in other:
                value = str(row[name]).strip()
                if name != "" and value != "":
                    attributes.append(
                        self.god.create_attribute(
                            AttributeType.SIMPLE, name, value)
                    )

            # get meta stuff
            if "_loc" in row:
                attributes.append(
                    self.god.create_attribute(
                        AttributeType.PDF_LOCATION, "location", (page_info.page, row["_loc"]))
                )

            # create aspect
            self.god.create_aspect(tag, page_info, tuple(attributes))


    def process_terminal_diagram(self, table: pd.DataFrame, page_info: PageInfo):
        # TODO very annoying thing, must be somehow avoided
        # detect left/right prefixed columns
        l_cols = [c for c in table.columns if c.startswith("_l")]
        r_cols = [c for c in table.columns if c.startswith("_r")]
        base_cols = [c for c in table.columns if not (c.startswith("_l") or c.startswith("_r"))]
        # remove prefixes
        def strip_prefix(c: str) -> str:
            return c.removeprefix("_l").removeprefix("_r")

        l_df = table[l_cols + base_cols].copy()
        l_df.columns = [strip_prefix(c) for c in l_df.columns] # type: ignore

        r_df = table[r_cols + base_cols].copy()
        r_df.columns = [strip_prefix(c) for c in r_df.columns] # type: ignore

        # TODO awful double mapping
        self.process_cable_diagram(l_df, page_info)
        self.process_cable_diagram(r_df, page_info)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    doc = pymupdf.open("pdfs/sample.pdf")
    god = God(configs=default_configs)
    page_settings = PageSettings("extraction_settings.json")
    processor = PageProcessor(god, page_settings)

    page = doc.load_page(56)  # Load the first page
    processor.run(page)
    print(god)
    for id, tgt in god.xtargets.items():
        print(tgt)
        # print(tgt.tag.get_aspects())
        print(tgt.attributes)

    print("links")
    for id, lnk in god.links.items():
        print(lnk)
        # print(tgt.tag.get_aspects())
        print(lnk.attributes)

    # for id, a in god.aspects.items():
    #     print(a)
