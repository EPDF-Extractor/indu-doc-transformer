from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd
import pymupdf  # type: ignore
import logging
from .common_page_utils import PageType, PageError, ErrorType

logger = logging.getLogger(__name__)
# In pt
PAPER_A3 = (1191.05, 842.39)


def get_clip_rect(w, h, x0, y0, w0, h0):
    return pymupdf.Rect(
        x0 / PAPER_A3[0] * w,
        y0 / PAPER_A3[1] * h,
        w0 / PAPER_A3[0] * w,
        h0 / PAPER_A3[1] * h,
    )


def demote_header(df: pd.DataFrame, header: list[str] | None = None):
    if header is None:
        header = [""] * len(df.columns)
    header_row = pd.DataFrame([df.columns], columns=header)
    df2 = pd.DataFrame(df.values, columns=header)
    return pd.concat([header_row, df2], ignore_index=True)


def promote_header(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(df.values[1:], columns=df.values[0])


def extract_spans(page, clip=None, tolerance = 0.1):
    spans = []
    raw = page.get_text("rawdict", sort=True, clip=clip)
    for block in raw.get('blocks', []):
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = None
                sx0, sy0, sx1, sy1 = span['bbox']
                if 'text' in span:
                    text = span.get('text')
                if 'chars' in span:
                    text = ''
                    prev = -1
                    for c in span['chars']:
                        # try to find overlaps
                        x0, _, x1, _ = c['bbox']
                        char = c.get('c', '')
                        # print(f"'{char}' {x0:.1f} {x1:.1f}", end="|")
                        # y = y0
                        if (x0 + (x1 - x0) * tolerance)  < prev:
                            # overlap detected - dump span
                            spans.append((sx0, sy0, prev, sy1, text))
                            text = ''
                            sx0 = x0
                            # print("@|", end="")
                            # print(f"overlap {char} {x0:.1f} {y0:.1f}")
                        text += char
                        prev = x1
                    # print(f" - {y0:.1f}")
                # print(text)
                spans.append((sx0, sy0, sx1, sy1, text))
    return spans


def detect_overlaps(text_blocks):
    overlaps = []

    rects = [(pymupdf.Rect(x0, y0, x1, y1), text)
             for (x0, y0, x1, y1, text, *_)
             in text_blocks]

    for i, (rect_i, text_i) in enumerate(rects):
        for j, (rect_j, text_j) in enumerate(rects[i+1:], start=i+1):
            if rect_i.intersects(rect_j):
                overlaps.append((text_i, text_j, rect_i, rect_j))

    return overlaps  # (text1, text2, cell_rect1, cell_rect2)


# TODO just for now (then try to fix errorxs)
def detect_row_overlaps(table, overlaps):
    affected_rows = []

    for _, _, rect1, rect2 in overlaps:
        for r, row in enumerate(table.rows):
            rect = pymupdf.Rect(row.bbox)
            if rect.intersects(pymupdf.Rect(rect1)) or rect.intersects(
                pymupdf.Rect(rect2)
            ):
                affected_rows.append(r)

    return affected_rows


def fix_row_overlaps(table, overlaps, method="center"):
    affected_rows = []

    for t1, t2, rect1, rect2 in overlaps:
        rect1_center = pymupdf.Point((rect1[0]+rect1[2])/2, (rect1[1]+rect1[3])/2)
        rect2_center = pymupdf.Point((rect2[0]+rect2[2])/2, (rect2[1]+rect2[3])/2)
        for r, row in enumerate(table.rows):
            rect = pymupdf.Rect(row.bbox)
            if rect.intersects(pymupdf.Rect(rect1)) or rect.intersects(
                pymupdf.Rect(rect2)
            ):
                repl_1 = None
                repl_2 = None
                # fix overlaps by centrer method
                for idx, c in enumerate(row.cells):
                    cell = pymupdf.Rect(c)
                    if cell.contains(rect1_center):
                        repl_1 = (idx, t1)
                    if cell.contains(rect2_center):
                        repl_2 = (idx, t2)
                affected_rows.append((r, row.bbox, repl_1, repl_2))

    return affected_rows
                


class TableExtractor:
    _type_handlers = {
        PageType.CONNECTION_LIST: lambda cls, page: cls.extract_connection_list(page),
        PageType.DEVICE_TAG_LIST: lambda cls, page: cls.extract_device_tag_list(page),
        PageType.DEVICE_LIST_DE: lambda cls, page: cls.extract_device_tag_list_de(page),
        PageType.CABLE_OVERVIEW: lambda cls, page: cls.extract_cable_overview(page),
        PageType.CABLE_PLAN: lambda cls, page: cls.extract_cable_plan(page),
        PageType.TOPOLOGY: lambda cls, page: cls.extract_topology(page),
        PageType.WIRES_PART_LIST: lambda cls, page: cls.extract_wires_part_list(page),
        PageType.TERMINAL_DIAGRAM: lambda cls, page: cls.extract_terminal_diagram(page),
        PageType.CABLE_DIAGRAM: lambda cls, page: cls.extract_cable_diagram(page),
        PageType.STRUCTURE_IDENTIFIER_OVERVIEW: lambda cls, page: cls.extract_structure_identifier_overview(page),
        PageType.PLC_DIAGRAM: lambda cls, page: cls.extract_plc_diagram(page),
    }

    @classmethod
    def extract(
        cls, pages: pymupdf.Page | list[pymupdf.Page], what
    ) -> tuple[Optional[pd.DataFrame], list[PageError]]:
        if isinstance(pages, pymupdf.Page):
            pages = [pages]  # make it a list
        logger.debug(f"Extracting '{what}' from {len(pages)} pages...")
        if len(pages) == 0:
            return None, []

        f = cls._type_handlers.get(what, None)
        assert f is not None, f"Specified table type '{what}' does not have a processor"
        # concat the rest
        tables = []
        errors: list[PageError] = []
        for p in pages:
            page_num = (p.number + 1) if p.number is not None else "unknown"
            logger.debug(f"Extracting '{what}' from page #{page_num}")
            try:
                t, msgs = f(cls, p)
                tables.append(t)
                errors += msgs
            except ValueError as ve:
                errors.append(PageError(f"{ve}", error_type=ErrorType.FAULT))
                logger.debug(
                    f"ValueError extracting '{what}' from page #{page_num}: {ve}"
                )
            except Exception as e:
                errors.append(PageError(f"{e}", error_type=ErrorType.UNKNOWN_ERROR))
                logger.debug(
                    f"Unexpected error extracting '{what}' from page #{page_num}: {e}"
                )
        #
        if len(tables) == 0:
            return None, errors
        table_df = pd.concat(tables, ignore_index=True)
        assert table_df.shape[1] == tables[0].shape[1], f"Table headers do not match"
        # fill all inconsistent empty stuff with empty line
        table_df = table_df.fillna('').map(
            lambda x: str(x).strip() if x is not None else '')
        # clean empty rows (some extractors do it also to prevent general data expansion)
        # required as sometimes detects "fake" rows
        table_df = table_df[(table_df != '').any(axis=1)]
        #
        return table_df, errors

    @staticmethod
    def extract_connection_list(page) -> tuple[pd.DataFrame, list[PageError]]:
        tables = list(page.find_tables())
        if len(tables) < 2:
            raise ValueError("No required tables found on the page")

        # TODO selection logic
        t1 = tables[1]
        t2 = tables[2] if len(tables) > 2 else None

        if t1 is None:
            raise ValueError("No required tables found on the page")

        # Preserve header - to_pandas breaks empty fields
        header = list(t1.header.names)
        df1 = t1.to_pandas()

        # Single table case
        if t2 is None:
            return df1

        # Two tables case - combine them
        if t1.col_count != t2.col_count:
            raise ValueError(
                f"Column count mismatch between tables: {t1.col_count} vs {t2.col_count}"
            )

        header_row = pd.DataFrame([t2.header.names], columns=header)
        df2 = pd.DataFrame(t2.to_pandas().values, columns=header)

        return pd.concat([df1, header_row, df2], ignore_index=True), []

    @staticmethod
    def extract_device_tag_list_de(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        # TODO cliprect check
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 33, 132, 1170, 780)))
        if not tables:
            raise ValueError(
                "No tables found in the specified clip area on the page")
        return tables[0].to_pandas()

    @staticmethod
    def extract_device_tag_list(page) -> tuple[pd.DataFrame, list[PageError]]:
        tables = list(page.find_tables())
        if not tables:
            raise ValueError("No tables found on the page")
        # TODO selection logic
        t = tables[1]
        df = t.to_pandas()
        #
        return pd.DataFrame(
            df.values[1:], columns=df.values[0]
        ), [] # use 1st row as header

    @staticmethod
    def extract_cable_overview(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 33, 33, 1170, 780)))
        if not tables:
            raise ValueError("No tables found on the page")
        df = tables[0].to_pandas()

        # use 1st row as header
        df = pd.DataFrame(df.values[1:], columns=df.values[0])

        # drop empty/None cols
        df = df.drop(
            columns=[col for col in df.columns if col is None or col == ""])

        # disjoin "from to" column
        col_to_drop = df.columns[1]
        split_cols = df[col_to_drop].str.split(" ", expand=True)
        if split_cols.shape[1] != 2:
            raise ValueError(
                f"Expected at most 2 columns after split 'from to' column, got {split_cols.shape[1]}, meaning some name had spaces in it!"
            )
        df[["from", "to"]] = split_cols
        df = df.drop(columns=[col_to_drop])
        # forward fill rows where designation is null, but src & dest are filled in
        # rows where designation is null but "from" and "to" are not
        mask = df[df.columns[0]].eq('') & df["from"].ne('') & df["to"].ne('')
        df.loc[mask, df.columns[0]] = df[df.columns[0]].replace('', pd.NA).ffill()

        # clean empty rows
        # TODO findot what chars to ignore: s.str.rstrip('.!? \n\t')
        # TODO unit test this
        df = df[df.apply(lambda row: row.astype(
            str).str.strip().ne('').any(), axis=1)]
        return df, []

    @staticmethod
    def extract_cable_plan(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )
        #
        # Will not work for German!
        # extract connections
        tables_left = list(page.find_tables(
            clip=get_clip_rect(w, h, 10, 98, 400, 780)))
        if not tables_left:
            raise ValueError("No required tables found on the page: left source info")
        df_left = tables_left[0].to_pandas()
        tables_right = list(
            page.find_tables(clip=get_clip_rect(w, h, 790, 98, 1185, 780))
        )
        if not tables_right:
            raise ValueError("No required tables found on the page: right target info")
        df_right = tables_right[0].to_pandas()
        df = pd.concat([df_left, df_right], axis=1)
        #
        # extract current device
        # 80 for English; 136 German!
        text = page.get_text(
            "text", clip=get_clip_rect(w, h, 114, 29, 400, 47))
        df["Cabel"] = text
        if len(text) == 0:
            raise ValueError("Failed to detect Cabel Tag")
        # other TODO unstable
        # tables_main = page.find_tables(strategy="text", clip=getClipRect(w, h, 33, 132, 1170, 203))
        # 120 for English; 230 German!
        tables_typ = list(
            page.find_tables(
                strategy="text", clip=get_clip_rect(w, h, 441, 120, 750, 780)
            )
        )
        typ = None
        if tables_typ:
            typ_header = list(
                tables_typ[0].header.names
            )  # Preserve header - to_pandas breaks it
            typ = tables_typ[0].to_pandas()
            # restore original names (.to_pandas breaks it)
            typ.columns = typ_header
            typ = demote_header(typ, ["Source conductor", "Target conductor"])
            typ = typ.iloc[::2].reset_index(drop=True)  # remove empty rows
        else:
            # fallback
            text_typ = page.get_text(
                "text", clip=get_clip_rect(w, h, 441, 120, 750, 780)
            )
            rows = [line for line in text_typ.split(
                "\n") if line.strip()]  # flat list
            rows = [
                rows[i: i + 2] for i in range(0, len(rows), 2)
            ]  # Group every 2 items into a row
            typ = pd.DataFrame(
                rows, columns=["Source conductor", "Target conductor"])
        df = pd.concat([df, typ], axis=1)

        # forward fill '=' stuff
        # rows where designation is null but "from" and "to" are not
        col_ids = [2, 9]
        df.iloc[:, col_ids] = df.iloc[:, col_ids].replace("=", pd.NA).ffill()

        return df, []

    @staticmethod
    def extract_topology(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 33, 75, 1170, 780)))
        # logger.debug_table_overview(tables)
        if not tables:
            raise ValueError("No required tables found on the page")

        return tables[0].to_pandas(), []

    @staticmethod
    def extract_wires_part_list(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 33, 70, 1170, 780)))
        # logger.debug_table_overview(tables)
        if not tables:
            raise ValueError("No required table found on the page")

        df = tables[0].to_pandas()
        return pd.DataFrame(
            df.values[1:], columns=df.values[0]
        ), []  # use 1st row as header

    @staticmethod
    def extract_cable_diagram(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )
        #
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 33, 70, 1170, 780)))
        if not tables:
            raise ValueError("No required table found on the page")
        # No way I can separate tables by coods - need to detect here
        df = tables[0].to_pandas()
        i = 0
        tables = []
        while i < len(df):
            # Detect start of a block: two rows with col2 & col3 missing
            if df.iloc[i, 1:3].isna().all() and df.iloc[i + 1, 1:3].isna().all():
                cable_name = df.iloc[i, 0].split(
                    " ")[-1]  # Here cable name is located
                i += 2
                # Ignore all info as duplicated and hard to extract

                header = df.iloc[i].tolist()
                i += 1

                # Gather table rows until next info block or end
                rows = []
                while i < len(df) and not (
                    df.iloc[i, 1:3].isna().all()
                    and i + 1 < len(df)
                    and df.iloc[i + 1, 1:3].isna().all()
                ):
                    rows.append(df.iloc[i].tolist())
                    i += 1

                table = pd.DataFrame(rows, columns=header)
                table["Cable"] = cable_name
                tables.append(table)
            else:
                i += 1

        return pd.concat(tables, ignore_index=True), []

    @staticmethod
    def extract_terminal_diagram(page) -> tuple[pd.DataFrame, list[PageError]]:
        errors: list[PageError] = []
        #
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )
        # Left side Cables
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 20, 33, 410, 237)))
        if not tables:
            raise ValueError(
                "No required tables found on the page: left cable info")
        # preserve header as to_pandas breaks it
        header = list(tables[0].header.names)
        df = tables[0].to_pandas()
        df.columns = header  # restore original names (.to_pandas breaks it)
        df_l_cables = demote_header(df)
        # Left side Cable Connections
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 20, 237, 410, 780)))
        if not tables:
            raise ValueError(
                "No required tables found on the page: left color info")
        df_l_conn = tables[0].to_pandas()
        # forward fill '=' stuff
        # rows where designation is null but "from" and "to" are not
        df.iloc[:, 0] = df.iloc[:, 0].replace("=", pd.NA).ffill()
        # Connections
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 410, 33, 780, 780)))
        if not tables:
            raise ValueError(
                "No required tables found on the page: connection info")
        # expand region of search beyond table in case of huge overlaps
        spans = extract_spans(page, clip=get_clip_rect(w, h, 20, 260, 1170, 780))
        overlaps = detect_overlaps(spans)
        overlapping_rows = []
        try:
            if overlaps:
                overlapping_rows = fix_row_overlaps(tables[0], overlaps)
        except:
            import traceback
            traceback.print_exc()
        df_center = tables[0].to_pandas()
        # Right side Cables
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 780, 33, 1170, 237)))
        if not tables:
            raise ValueError(
                "No required tables found on the page: right cable info")
        # preserve header as to_pandas breaks it
        header = list(tables[0].header.names)
        df = tables[0].to_pandas()
        df.columns = header  # restore original names (.to_pandas breaks it)
        df_r_cables = demote_header(df)
        # Right side Cable Connections
        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 780, 237, 1170, 780)))
        if not tables:
            raise ValueError(
                "No required tables found on the page: right color info")
        df_r_conn = tables[0].to_pandas()

        # here I have to do preprocessing to make a single df
        strip_info = df_center.columns[0]
        strip_name = strip_info.splitlines()[1]

        df = promote_header(df_center)

        # Apply overlaps fix 
        if overlapping_rows:
            for row, _, repl1, repl2  in overlapping_rows:
                # -2 as promote_header & index counts from 1 in detect_row_overlaps
                row -= 2
                # apply replacements
                if repl1:
                    msg = f"row #{row} overlap detected: replaced col #{repl1[0]}: {df.iloc[row, repl1[0]]} -> {repl1[1]}"
                    errors.append(PageError(msg, error_type=ErrorType.INFO))
                    logger.warning(msg)
                    df.iloc[row, repl1[0]] = repl1[1]
                if repl2:
                    msg = f"row #{row} overlap detected: replaced col #{repl2[0]}: {df.iloc[row, repl2[0]]} -> {repl2[1]}"
                    errors.append(PageError(msg, error_type=ErrorType.INFO))
                    logger.warning(msg)
                    df.iloc[row, repl2[0]] = repl2[1]
                # log
                if not (repl1 and repl2):
                    msg = f"row #{row} overlap detected: could not repair (fully)"
                    errors.append(PageError(msg, error_type=ErrorType.WARNING))
                    logger.warning(msg)

        #
        def transform_dataframe(df_cables, df_conn):
            rows = []
            number_cols = [col for col in df_conn.columns if col.isdigit()]
            non_number_cols = [
                col for col in df_conn.columns if col not in number_cols]
            columns = ["Cable", "Color"] + non_number_cols
            # for each connection
            for idx, row in df_conn.iterrows():
                non_number_values = row[non_number_cols].tolist()
                cable_info_list = []
                color_list = []
                for col in number_cols:
                    color = row[col]
                    if pd.notna(color) and color.strip() != "":
                        # assume it is convertible to int as we did isdigit
                        cable_index = int(col) - 1
                        # As in the same row cable tag & info are located -> select only tag
                        # TODO might be wrong as cable tag might have spaces (?)
                        cable_info = df_cables.iloc[cable_index, 1].split(" ")[
                            0]
                        # Extract a TAG from cable_info
                        cable_info_list.append(cable_info)
                        color_list.append(color)
                #
                if len(cable_info_list) > 1:
                    msg = f"row #{idx} partially ignored: has multiple cable connections"
                    errors.append(PageError(msg, error_type=ErrorType.WARNING))
                    logger.warning(msg)
                # 
                rows.append(
                    [";".join(cable_info_list), ";".join(color_list)]
                    + non_number_values
                )
            return pd.DataFrame(rows, columns=columns)

        # Check if the number of rows in the transformed dataframes matches the number of rows in df
        left_transformed = transform_dataframe(df_l_cables, df_l_conn)
        right_transformed = transform_dataframe(df_r_cables, df_r_conn)
        if left_transformed.shape[0] != df.shape[0]:
            raise ValueError(
                f"Left cable assignment table ({left_transformed.shape[0]}) does not match connections ({df.shape[0]})"
            )
        if right_transformed.shape[0] != df.shape[0]:
            raise ValueError(
                f"Right cable assignment table ({right_transformed.shape[0]}) does not match connections ({df.shape[0]})"
            )

        # Prepend left_transformed, append right_transformed
        df = pd.concat(
            [
                left_transformed.reset_index(drop=True),
                df.reset_index(drop=True),
                right_transformed.reset_index(drop=True),
            ],
            axis=1,
        )

        # clean empty rows
        df = df[df.apply(lambda row: row.astype(
            str).str.strip().ne('').any(), axis=1)]
        # insert strip name as 1st column
        df.insert(0, "Strip", strip_name)

        return df, errors
    

    @staticmethod
    def extract_structure_identifier_overview(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 32, 70, 1170, 780)))
        # logger.debug_table_overview(tables)
        if not tables:
            raise ValueError("No required tables found on the page")
        
        return tables[0].to_pandas(), []


    @staticmethod
    def extract_plc_diargam(page) -> tuple[pd.DataFrame, list[PageError]]:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(
            clip=get_clip_rect(w, h, 32, 70, 1170, 780)))
        # logger.debug_table_overview(tables)
        if not tables:
            raise ValueError("No required tables found on the page")

        # get rid of table top line
        df = tables[0].to_pandas()
        df = promote_header(df)

        # get rid of empty rows
        df = df[df.apply(lambda row: row.astype(
            str).str.strip().ne('').any(), axis=1)]
        
        # forward fill Device Tag
        df.iloc[:, 0] = df.iloc[:, 0].replace("", pd.NA).ffill()
        
        return df, []


if __name__ == "__main__":
    doc = pymupdf.open("pdfs/sample.pdf")

    df = TableExtractor.extract(doc[82:83], PageType.CABLE_DIAGRAM)
