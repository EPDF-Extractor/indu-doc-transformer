from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd
import pymupdf  # type: ignore
import logging
from .common_page_utils import PageType, PageError, ErrorType
from .extraction_settings import rect, PageSetup, TableSetup, ExtractionSettings

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


def promote_header(df: pd.DataFrame, level=1) -> pd.DataFrame:
    return pd.DataFrame(df.values[level:], columns=df.values[level-1])


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


def detect_overlaps(text_blocks) -> list[tuple[str, str, rect, rect]]:
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


def fix_row_overlaps(table, overlaps: list[tuple[str, str, rect, rect]], method="center") -> list[tuple[int, rect, tuple[int, str], tuple[int, str]]]:
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

    return affected_rows # type: ignore


def to_df_with_loc(
    table: pymupdf.Table, 
    loc_col_name: str = "_loc", 
    row_offset: int = 0, 
    header: list[str] = []
) -> pd.DataFrame:
    ''' extracts df from pymupdf table. 
    Select header row using row_offset: (row_offset+1) row is taken as header
    Adds loc_col_name attr with row bbox to each row. Start loc_col_name with '_'
    Can create None or empty cells. Can create phantom rows and columns
    '''
    if row_offset < -1:
        raise ValueError(
            f"Can not demote on {-row_offset} levels")
    
    # In case of demotion to_pandas breaks table header to make it unq - save original
    old_header = list(table.header.names)
    #
    df = table.to_pandas(header=False)
    # promote/demote
    if row_offset < 0:
        df.columns = old_header # only for demotion so values are preserved
        df = demote_header(df)
    elif row_offset > 1:
        df = promote_header(df, row_offset)
    # overwrite header
    if header:
        df.columns = header

    # get locations
    bboxes = [r.bbox for r in table.rows]
    # very weird thing here: sometimes pymupdf includes header bbox into table.rows and sometimes not
    # fix: if already has header - do not add it:
    if table.row_count > 0 and not np.allclose(table.rows[0].bbox, table.header.bbox, rtol=1e-9, atol=1e-9):
        bboxes = [table.header.bbox] + bboxes
    # attach _loc
    df[loc_col_name] = bboxes[row_offset+1:]  
    return df      


class TableExtractor:

    @classmethod
    def get_extractor(cls, what):
        _type_handlers = {
            PageType.CABLE_PLAN: cls.extract_cable_plan,
            PageType.TERMINAL_DIAGRAM: cls.extract_terminal_diagram,
            PageType.CABLE_DIAGRAM: cls.extract_cable_diagram,
        }
        return _type_handlers.get(what, cls.extract_main_stub)

    @classmethod
    def extract(
        cls, 
        pages: pymupdf.Page | list[pymupdf.Page], 
        what: PageType,
        setup: PageSetup
    ) -> tuple[Optional[pd.DataFrame], list[PageError]]:
        if isinstance(pages, pymupdf.Page):
            pages = [pages]  # make it a list
        logger.debug(f"Extracting '{what}' from {len(pages)} pages...")
        if len(pages) == 0:
            return None, []

        # concat the rest
        tables = []
        errors: list[PageError] = []
        for p in pages:
            page_num = (p.number + 1) if p.number is not None else "unknown"
            logger.info(f"Extracting '{what}' from page #{page_num}")
            try:
                # 1st: Do generalized table extraction
                dfs, msgs = extract_tables(p, setup)
                # 2nd: Do table speciefic processing
                t, msgs = cls.get_extractor(what)(dfs)
                tables.append(t)
                errors += msgs
            except ValueError as ve:
                errors.append(PageError(f"{ve}", error_type=ErrorType.FAULT))
                logger.warning(
                    f"ValueError extracting '{what}' from page #{page_num}: {ve}"
                )
            except Exception as e:
                errors.append(PageError(f"{e}", error_type=ErrorType.UNKNOWN_ERROR))
                logger.warning(
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
    def extract_main_stub(dfs: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[PageError]]:
        if "main" not in dfs:
            raise ValueError(f"Required table was not found: {"main"}")
        return dfs["main"], []


    # TODO can not detect in sample doc
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
    def extract_cable_diagram(dfs: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[PageError]]:
        if "main" not in dfs:
            raise ValueError(f"Required table was not found: {"main"}")
        df = dfs["main"]
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
    def extract_terminal_diagram(dfs: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[PageError]]:
        errors: list[PageError] = []
        #
        df_center   = dfs["main"]
        df_r_cables = dfs["r_cables"]
        df_r_conn   = dfs["r_conn"]
        df_l_cables = dfs["l_cables"]
        df_l_conn   = dfs["l_conn"]

        # here I have to do preprocessing to make a single df
        strip_info = df_center.columns[0]
        strip_name = strip_info.splitlines()[1]

        df = promote_header(df_center)

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


def extract_tables(page: pymupdf.Page, page_setup: PageSetup) -> tuple[dict[str, pd.DataFrame], list[PageError]]:
    ''' Universal table extractor which behavior is specified and extended by PageSetup '''

    errors: list[PageError] = []
    res: dict[str, pd.DataFrame] = {}
    for key, table_setup in page_setup.tables.items():
        print(table_setup.lines)
        tables = list(page.find_tables(clip=table_setup.roi, add_lines=table_setup.lines))
        if not tables:
            raise ValueError(
                f"No required table(s) found on the page: {key}")
        
        if len(tables) > table_setup.expected_num_tables:
            raise ValueError(
                f"Expected <= {table_setup.expected_num_tables} tables, found more: {len(tables)}")

        # do overlap detection if required - expensive! - doesnt work with >1 tables
        overlap_fixes = []
        if table_setup.overlap_test_roi:
            if len(tables) > 1:
                raise ValueError(
                    f"Overlap detection does not work witn many tables")
            spans = extract_spans(page, clip=table_setup.overlap_test_roi)
            overlaps = detect_overlaps(spans)
            overlap_fixes = fix_row_overlaps(tables[0], overlaps) if overlaps else []

        # test header size mathch
        sz = tables[0].col_count
        if sz != len(table_setup.columns):
            print(repr(tables[0]))
            raise ValueError(
                f"Expected {len(table_setup.columns)} columns, found {sz}")
        
        # assign new header out of table_setup.columns
        columns = list(table_setup.columns.keys())
        
        # to pandas
        dfs = [to_df_with_loc(tables[0], row_offset=table_setup.row_offset, header=columns)]
        for t in tables[1:]:
            # test header size mathch
            if sz != t.col_count:
                raise ValueError(
                    f"Expected {sz} columns, found {t.col_count}")
            # get promotion/demotion level
            lvl = table_setup.row_offset + (-1 if table_setup.on_many_no_header else 0)
            # convert to df
            df = to_df_with_loc(t, row_offset=lvl, header=columns)
            dfs.append(df)

        df = pd.concat(dfs, ignore_index=True)

        # apply overlap fix
        if overlap_fixes:
            for row, _, repl1, repl2 in overlap_fixes:
                # as index counts from 1 in detect_row_overlaps
                row -= 1 + table_setup.row_offset
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

        # remove ignored columns
        ignored = [k for k, v in table_setup.columns.items() if not v]
        df = df.drop(columns=ignored)

        # keep only rows where there is at least one non-empty string value
        # 1. ignore meta cols
        cols = [col for col in df.columns if not col.startswith('_')]
        df = df[df[cols].apply(lambda row: row.notnull() & (row != ''), axis=1).any(axis=1)]

        # do forward fill (? here)

        # attach to res
        res[key] = df

    return res, errors    


if __name__ == "__main__":
    doc = pymupdf.open("pdfs/sample.pdf")

    df = TableExtractor.extract(doc[82:83], PageType.CABLE_DIAGRAM)
