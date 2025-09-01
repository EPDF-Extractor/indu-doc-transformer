from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd
import pymupdf
import logging
from .common_page_utils import PageType

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


def demote_header(df, header=None):
    if header is None:
        header = [""] * len(df.columns)
    header_row = pd.DataFrame([df.columns], columns=header)
    df2 = pd.DataFrame(df.values, columns=header)
    return pd.concat([header_row, df2], ignore_index=True)


def promote_header(df):
    return pd.DataFrame(df.values[1:], columns=df.values[0])


def forward_fill(df, column, replacement="="):
    saved = None
    new_values = []
    for val in df[column]:
        if val != replacement:
            saved = val
            new_values.append(val)
        else:
            if saved is None:
                raise ValueError(
                    f"Forward fill table column {column} has {replacement} before any value was specified"
                )
            new_values.append(saved)
    df[column] = new_values
    return df


def detect_overlaps(text_blocks):
    overlaps = []

    for i, (x0_i, y0_i, x1_i, y1_i, text_i, _, _, _) in enumerate(text_blocks):
        for j, (x0_j, y0_j, x1_j, y1_j, text_j, _, _, _) in enumerate(text_blocks):
            if i >= j:
                continue  # avoid double-checking same pair
            # check for intersection
            if not (x1_i <= x0_j or x1_j <= x0_i or y1_i <= y0_j or y1_j <= y0_i):
                overlaps.append(
                    (text_i, text_j, (x0_i, y0_i, x1_i, y1_i), (x0_j, y0_j, x1_j, y1_j))
                )

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
    }

    @classmethod
    def extract(
        cls, pages: pymupdf.Page | list[pymupdf.Page], what
    ) -> Optional[pd.DataFrame]:
        if isinstance(pages, pymupdf.Page):
            pages = [pages]  # make it a list
        logger.debug(f"Extracting '{what}' from {len(pages)} pages...")
        if len(pages) == 0:
            return None

        f = cls._type_handlers.get(what, None)
        assert f is not None, f"Specified table type '{what}' does not have a processor"
        # concat the rest
        tables = []
        for p in pages:
            logger.debug(f"Extracting '{what}' from page #{p.number + 1}")
            try:
                t = f(cls, p)
                if t is not None:
                    tables.append(t)
                else:
                    logger.debug(
                        f"Could not extract '{what}' from page #{p.number + 1}: got None"
                    )
            except ValueError as ve:
                logger.debug(
                    f"ValueError extracting '{what}' from page #{p.number + 1}: {ve}"
                )
            except Exception as e:
                logger.debug(
                    f"Unexpected error extracting '{what}' from page #{p.number + 1}: {e}"
                )
        #
        if len(tables) == 0:
            return None
        table_df = pd.concat(tables, ignore_index=True)
        assert table_df.shape[1] == tables[0].shape[1], f"Table headers do not match"
        return table_df

    @staticmethod
    def extract_connection_list(page):
        tables = list(page.find_tables())
        if len(tables) < 2:
            raise ValueError("No required tables found on the page")

        # TODO selection logic
        t1 = tables[1]
        t2 = tables[2] if len(tables) > 2 else None

        if t1 is None:
            return None

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

        return pd.concat([df1, header_row, df2], ignore_index=True)

    @staticmethod
    def extract_device_tag_list_de(page) -> pd.DataFrame:
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        # TODO cliprect check
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 33, 132, 1170, 780)))
        if not tables:
            raise ValueError("No tables found in the specified clip area on the page")
        return tables[0].to_pandas()

    @staticmethod
    def extract_device_tag_list(page):
        tables = list(page.find_tables())
        if not tables:
            raise ValueError("No tables found on the page")
        # TODO selection logic
        t = tables[1]
        df = t.to_pandas()
        #
        return pd.DataFrame(
            df.values[1:], columns=df.values[0]
        )  # use 1st row as header

    @staticmethod
    def extract_cable_overview(page):
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(clip=get_clip_rect(w, h, 33, 33, 1170, 780)))
        if not tables:
            raise ValueError("No tables found on the page")
        df = tables[0].to_pandas()

        # use 1st row as header
        df = pd.DataFrame(df.values[1:], columns=df.values[0])

        # drop empty/None cols
        df = df.drop(columns=[col for col in df.columns if col is None or col == ""])

        # disjoin "from to" column
        col_to_drop = df.columns[1]
        split_cols = df[col_to_drop].str.split(" ", expand=True)
        if split_cols.shape[1] != 2:
            raise ValueError(
                f"Expected at most 2 columns after split, got {split_cols.shape[1]}, meaning some name had spaces in it!"
            )
        df[["from", "to"]] = split_cols
        df = df.drop(columns=[col_to_drop])
        return df

    @staticmethod
    def extract_cable_plan(page):
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )
        #
        # Will not work for German!
        # extract connections
        tables_left = list(page.find_tables(clip=get_clip_rect(w, h, 10, 98, 400, 780)))
        if not tables_left:
            raise ValueError("No required tables found on the page")
        df_left = tables_left[0].to_pandas()
        tables_right = list(
            page.find_tables(clip=get_clip_rect(w, h, 790, 98, 1185, 780))
        )
        if not tables_right:
            raise ValueError("No required tables found on the page")
        df_right = tables_right[0].to_pandas()
        df = pd.concat([df_left, df_right], axis=1)
        #
        # extract current device
        # 80 for English; 136 German!
        text = page.get_text("text", clip=get_clip_rect(w, h, 114, 29, 400, 47))
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
            typ.columns = typ_header  # restore original names (.to_pandas breaks it)
            typ = demote_header(typ, ["Source conductor", "Target conductor"])
            typ = typ.iloc[::2].reset_index(drop=True)  # remove empty rows
        else:
            # fallback
            text_typ = page.get_text(
                "text", clip=get_clip_rect(w, h, 441, 120, 750, 780)
            )
            rows = [line for line in text_typ.split("\n") if line.strip()]  # flat list
            rows = [
                rows[i : i + 2] for i in range(0, len(rows), 2)
            ]  # Group every 2 items into a row
            typ = pd.DataFrame(rows, columns=["Source conductor", "Target conductor"])
        df = pd.concat([df, typ], axis=1)

        # TODO do forward fill?
        return df

    @staticmethod
    def extract_topology(page):
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(clip=get_clip_rect(w, h, 33, 75, 1170, 780)))
        # logger.debug_table_overview(tables)
        if not tables:
            raise ValueError("No required tables found on the page")

        return tables[0].to_pandas()

    @staticmethod
    def extract_wires_part_list(page):
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )

        tables = list(page.find_tables(clip=get_clip_rect(w, h, 33, 70, 1170, 780)))
        # logger.debug_table_overview(tables)
        if not tables:
            raise ValueError("No required tables found on the page")

        df = tables[0].to_pandas()
        return pd.DataFrame(
            df.values[1:], columns=df.values[0]
        )  # use 1st row as header

    @staticmethod
    def extract_cable_diagram(page):
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )
        #
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 33, 70, 1170, 780)))
        if not tables:
            raise ValueError("No required tables found on the page")
        # No way I can separate tables by coods - need to detect here
        df = tables[0].to_pandas()
        df = df.replace({None: np.nan})
        i = 0
        tables = []
        while i < len(df):
            # Detect start of a block: two rows with col2 & col3 missing
            if df.iloc[i, 1:3].isna().all() and df.iloc[i + 1, 1:3].isna().all():
                cable_name = df.iloc[i, 0].split(" ")[-1]  # Here cable name is located
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

        return pd.concat(tables, ignore_index=True)

    @staticmethod
    def extract_terminal_diagram(page):
        w = page.rect.width
        h = page.rect.height
        if w <= h:
            raise ValueError(
                f"Album orientation expected, found: width={w}, height={h}."
            )
        # Left side Cables
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 20, 33, 410, 237)))
        if not tables:
            raise ValueError("No required tables found on the page: left cable info")
        header = list(tables[0].header.names)  # preserve header as to_pandas breaks it
        df = tables[0].to_pandas()
        df.columns = header  # restore original names (.to_pandas breaks it)
        df_l_cables = demote_header(df)
        # Left side Cable Connections
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 20, 237, 410, 780)))
        if not tables:
            raise ValueError("No required tables found on the page: left color info")
        df_l_conn = tables[0].to_pandas()
        # Connections
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 410, 33, 780, 780)))
        if not tables:
            raise ValueError("No required tables found on the page: connection info")
        overlaps = detect_overlaps(
            page.get_text("words", clip=get_clip_rect(w, h, 410, 33, 780, 780))
        )
        overlapping_rows = []
        if overlaps:
            overlapping_rows = detect_row_overlaps(tables[0], overlaps)
        df_center = tables[0].to_pandas()
        # Right side Cables
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 780, 33, 1170, 237)))
        if not tables:
            raise ValueError("No required tables found on the page: right cable info")
        header = list(tables[0].header.names)  # preserve header as to_pandas breaks it
        df = tables[0].to_pandas()
        df.columns = header  # restore original names (.to_pandas breaks it)
        df_r_cables = demote_header(df)
        # Right side Cable Connections
        tables = list(page.find_tables(clip=get_clip_rect(w, h, 780, 237, 1170, 780)))
        if not tables:
            raise ValueError("No required tables found on the page: left color info")
        df_r_conn = tables[0].to_pandas()

        # here I have to do preprocessing to make a single df
        strip_info = df_center.columns[0]
        strip_name = strip_info.splitlines()[1]

        df = promote_header(df_center)

        # For now I will just delete overlapping rows
        if overlapping_rows:
            logger.debug(
                "OVERLAP DETECTED! ERROR HANDLING IS NOT DONE YET! FOR NOW JUST IGNORED!"
            )
            # -2 as promote_header & index counts from 1 in detect_row_overlaps
            adjusted_rows = [i - 2 for i in overlapping_rows]
            df = df.drop(index=adjusted_rows).reset_index(drop=True)
            df_l_conn = df_l_conn.drop(index=adjusted_rows).reset_index(drop=True)
            df_r_conn = df_r_conn.drop(index=adjusted_rows).reset_index(drop=True)

        #
        def transform_dataframe(df_cables, df_conn):
            rows = []
            number_cols = [col for col in df_conn.columns if col.isdigit()]
            non_number_cols = [col for col in df_conn.columns if col not in number_cols]
            columns = ["Cable", "Color"] + non_number_cols
            # for each connection
            for _, row in df_conn.iterrows():
                non_number_values = row[non_number_cols].tolist()
                cable_info_list = []
                color_list = []
                for col in number_cols:
                    color = row[col]
                    if pd.notna(color) and color.strip() != "":
                        # assume it is convertible to int as we did isdigit
                        cable_index = int(col) - 1
                        # TODO might be wrong as cable tag might have spaces (?)
                        cable_info = df_cables.iloc[cable_index, 1].split(" ")[0]
                        # Extract a TAG from cable_info
                        cable_info_list.append(cable_info)
                        color_list.append(color)
                rows.append(
                    ["; ".join(cable_info_list), "; ".join(color_list)]
                    + non_number_values
                )
            return pd.DataFrame(rows, columns=columns)

        # Check if the number of rows in the transformed dataframes matches the number of rows in df
        left_transformed = transform_dataframe(df_l_cables, df_l_conn)
        right_transformed = transform_dataframe(df_r_cables, df_r_conn)
        if left_transformed.shape[0] != df.shape[0]:
            raise ValueError(
                f"Left cable assignment ({left_transformed.shape[0]}) does not match connections ({df.shape[0]})"
            )
        if right_transformed.shape[0] != df.shape[0]:
            raise ValueError(
                f"Right cable assignment ({right_transformed.shape[0]}) does not match connections ({df.shape[0]})"
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
        df = df.where(df != "").dropna(how="all")
        # insert strip name as 1st column
        df.insert(0, "Strip", strip_name)

        return df


if __name__ == "__main__":
    doc = pymupdf.open("pdfs/sample.pdf")

    df = TableExtractor.extract(doc[72:76], PageType.CABLE_DIAGRAM)
    logger.debug(df.iloc[0])
    logger.debug(df)
