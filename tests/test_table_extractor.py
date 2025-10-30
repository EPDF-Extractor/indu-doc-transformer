import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from indu_doc.plugins.eplan_pdfs.table_extractor import (
    demote_header,
    promote_header,
    extract_spans,
    detect_overlaps,
    detect_row_overlaps,
    fix_row_overlaps,
    to_df_with_loc,
    extract_table,
    extract_text,
    extract_tables,
    TableExtractor
) 

from indu_doc.plugins.eplan_pdfs.common_page_utils import (
    PageError,
    ErrorType,
    PageType
)
from indu_doc.plugins.eplan_pdfs.page_settings import PageSetup, TableSetup

def make_mock_row(bbox, cells=None):
    r = MagicMock()
    r.bbox = bbox
    r.cells = cells or []
    return r

def make_mock_table(rows):
    t = MagicMock()
    t.rows = rows
    t.row_count = len(rows)
    return t

class TestPromoteDemoteHeader:
    def test_demote_header_basic(self):
        df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        result = demote_header(df)
        # Header row inserted
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert result.iloc[0, 0] == "A"
        assert result.iloc[1, 0] == 1

    def test_demote_header_custom_header(self):
        df = pd.DataFrame({"A": [1], "B": [2]})
        header = ["X", "Y"]
        result = demote_header(df, header)
        assert list(result.columns) == header
        assert result.iloc[0, 0] == "A"

    def test_promote_header_basic(self):
        df = pd.DataFrame([[ "A", "B"], [1, 2]])
        result = promote_header(df, level=1)
        assert list(result.columns) == ["A", "B"]
        assert result.iloc[0,0] == 1


class TestExtractSpans:
    def test_extract_spans_text_and_chars(self):
        page = MagicMock()
        page.get_text.return_value = {
            "blocks": [
                {"lines": [
                    {"spans":[{"bbox": [0,0,10,10], "text": "abc"}]}
                ]}
            ]
        }
        spans = extract_spans(page)
        assert spans[0][:4] == (0,0,10,10)
        assert spans[0][4] == "abc"

    def test_extract_spans_chars_only(self):
        page = MagicMock()
        page.get_text.return_value = {
            "blocks": [
                {"lines": [
                    {"spans":[{"bbox": [0,0,10,10], "chars": [{"bbox": [0,0,5,5], "c":"a"},{"bbox":[6,0,10,5],"c":"b"}]}]}
                ]}
            ]
        }
        spans = extract_spans(page)
        # chars concatenated
        assert any("ab" in s[4] for s in spans)


class TestRowOverlaps:
    def test_detect_overlaps_simple(self):
        text_blocks = [
            (0,0,5,5,"a"),
            (3,3,6,6,"b"),
            (10,10,15,15,"c")
        ]
        overlaps = detect_overlaps(text_blocks)
        # only "a" and "b" overlap
        assert any("a" in t and "b" in t2 for t,t2,_,_ in overlaps)
        # "c" does not overlap
        assert not any("c" in t for t,_,_,_ in overlaps)

    def test_detect_row_overlaps(self):
        row1 = make_mock_row((0,0,5,5))
        row2 = make_mock_row((6,0,10,5))
        table = make_mock_table([row1,row2])
        overlaps = [(None,None,(1,1,4,4),(7,0,9,4))]
        affected = detect_row_overlaps(table, overlaps)
        # row 0 intersects rect1, row1 intersects rect2
        assert set(affected) == {0,1}

    def test_fix_row_overlaps(self):
        # mock table with cells
        cell1 = (0,0,5,5)
        cell2 = (6,0,10,5)
        row1 = make_mock_row((0,0,10,5), cells=[cell1,cell2])
        table = make_mock_table([row1])
        overlaps = [("t1","t2",(1,1,4,4),(7,0,9,4))]
        affected = fix_row_overlaps(table, overlaps)
        # should produce affected_rows with replacements
        assert affected[0][2][1] == "t1"
        assert affected[0][3][1] == "t2"


class TestToDfWithLoc:
    def make_mock_table(self, header_names, header_bbox, row_bboxes):
        """Helper to create a mocked pymupdf.Table"""
        table = MagicMock()
        table.header.names = header_names
        table.header.bbox = header_bbox
        table.rows = [MagicMock(bbox=bbox) for bbox in row_bboxes]
        table.row_count = len(table.rows)
        table.to_pandas.return_value = pd.DataFrame([[i+j+1 for i in range(len(header_names))] for j in range(len(row_bboxes))], columns=header_names)
        return table

    def test_basic_table(self):
        table = self.make_mock_table(["A","B"], (0,0,1,1), [(0,1,1,2)])
        df = to_df_with_loc(table)
        # Columns include _loc
        assert "_loc" in df.columns
        # _loc of first row is 1st row bbox
        assert df["_loc"].iloc[0] == (0,1,1,2)
        # Columns
        assert list(df.columns) == ["A", "B", "_loc"]
        # Data shape
        assert df.shape[0] == 1  # just 1 row

    def test_custom_header_override(self):
        table = self.make_mock_table(["A","B"], (0,0,1,1), [(0,1,1,2)])
        df = to_df_with_loc(table, header=["X","Y"])
        assert list(df.columns) == ["X","Y", "_loc"]

    def test_multiple_rows(self):
        table = self.make_mock_table(["A","B"], (0,0,1,1), [(0,1,1,2), (0,2,1,3), (0,3,1,4)])
        df = to_df_with_loc(table)
        # Number of rows = header + table rows
        assert df.shape[0] == 3
        # _loc column matches correct bboxes
        expected_bboxes = [(0,1,1,2), (0,2,1,3), (0,3,1,4)]
        assert list(df["_loc"]) == expected_bboxes

    def test_row_offset_promotes_header(self):
        table = self.make_mock_table(["A","B","C"], (0,0,3,1), [(0,1,3,2), (0,2,3,3)])
        # offset = 1 promotes first row as header
        df = to_df_with_loc(table, row_offset=1)
        # Check that df columns are taken from first row values
        assert df.columns.tolist() == [1,2,3, "_loc"]

    def test_row_offset_negative_demotes_header(self):
        table = self.make_mock_table(["A","B"], (0,0,2,1), [(0,1,2,2)])
        df = to_df_with_loc(table, row_offset=-1)
        # Columns are dropped
        assert df.columns.tolist() == ["","","_loc"]

    def test_loc_column_custom_name(self):
        table = self.make_mock_table(["A","B"], (0,0,1,1), [(0,1,1,2)])
        df = to_df_with_loc(table, loc_col_name="_position")
        assert "_position" in df.columns
        assert "_loc" not in df.columns

    def test_empty_table(self):
        table = self.make_mock_table(["A","B"], (0,0,1,1), [])
        df = to_df_with_loc(table)
        # Only header row remains
        assert df.shape[0] == 0
        assert "_loc" in df.columns

    def test_invalid_negative_offset(self):
        table = self.make_mock_table(["A","B"], (0,0,1,1), [(0,1,1,2)])
        with pytest.raises(ValueError):
            to_df_with_loc(table, row_offset=-5)


class TestExtractTable:

    def make_mock_table(self, col_count=3, row_count=2):
        table = MagicMock()
        table.col_count = col_count
        table.row_count = row_count
        # mock rows for to_df_with_loc
        table.rows = [MagicMock(bbox=(i, i, i+1, i+1)) for i in range(row_count)]
        # simulate to_df_with_loc
        table.to_pandas.return_value = pd.DataFrame(
            [[i+j+1 for j in range(col_count)] for i in range(row_count)]
        )
        return table

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_no_tables_found(self, mock_to_df):
        page = MagicMock()
        page.find_tables.return_value = []
        table_setup = TableSetup()
        with pytest.raises(ValueError, match="No required table"):
            extract_table(page, "key", table_setup)

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_too_many_tables_error(self, mock_to_df):
        page = MagicMock()
        page.find_tables.return_value = [MagicMock(), MagicMock()]
        table_setup = TableSetup(expected_num_tables=1)
        with pytest.raises(ValueError, match="Expected <= 1 tables"):
            extract_table(page, "key", table_setup)

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_spans")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.detect_overlaps")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.fix_row_overlaps")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_overlap_detection_single_table(self, mock_to_df, mock_fix, mock_detect, mock_extract):
        table = self.make_mock_table()
        page = MagicMock()
        page.find_tables.return_value = [table]

        # simulate overlap detection
        mock_extract.return_value = [(0,0,1,1,'text')]
        mock_detect.return_value = [(1,2,(0,0,1,1),(0,0,1,1))]
        mock_fix.return_value = [(1, table.rows[0].bbox, (0,'fixed1'), (1,'fixed2'))]
        mock_to_df.return_value = pd.DataFrame([[1,2,3],[4,5,6]], columns=['A','B','C'])

        table_setup = TableSetup(columns={'A':(True,), 'B':(True,), 'C':(True,)},
                                 overlap_test_roi=(0,0,1,1))
        df, errors = extract_table(page, "key", table_setup)

        # should apply fixes
        assert any(isinstance(e, PageError) for e in errors)
        assert df.shape[1] == 3

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_spans")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.detect_overlaps")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.fix_row_overlaps")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_overlap_detection_multi_table_fails(self, mock_to_df, mock_fix, mock_detect, mock_extract):
        table1 = self.make_mock_table(col_count=3)
        table2 = self.make_mock_table(col_count=3)
        page = MagicMock()
        page.find_tables.return_value = [table1, table2]

        # simulate overlap detection
        mock_extract.return_value = [(0,0,1,1,'text')]
        mock_detect.return_value = [(1,2,(0,0,1,1),(0,0,1,1))]
        mock_fix.return_value = [(1, table1.rows[0].bbox, (0,'fixed1'), (1,'fixed2'))]
        mock_to_df.return_value = pd.DataFrame([[1,2,3],[4,5,6]], columns=['A','B','C'])

        table_setup = TableSetup(columns={'A':(True,), 'B':(True,), 'C':(True,)},
                                 overlap_test_roi=(0,0,1,1), expected_num_tables=2)
        with pytest.raises(ValueError, match="Overlap detection does not work"):
            df, errors = extract_table(page, "key", table_setup)

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_column_count_mismatch(self, mock_to_df):
        table = self.make_mock_table(col_count=2)
        page = MagicMock()
        page.find_tables.return_value = [table]
        table_setup = TableSetup(columns={'A':(True,), 'B':(True,), 'C':(True,)})
        with pytest.raises(ValueError, match="Expected 3 columns"):
            extract_table(page, "key", table_setup)

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_column_count_mismatch_multiple_tables(self, mock_to_df):
        table1 = self.make_mock_table(col_count=3)
        table2 = self.make_mock_table(col_count=2)
        page = MagicMock()
        page.find_tables.return_value = [table1, table2]
        table_setup = TableSetup(columns={'A':(True,), 'B':(True,), 'C':(True,)}, expected_num_tables=2)
        with pytest.raises(ValueError, match="Expected 3 columns"):
            extract_table(page, "key", table_setup)


    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_multiple_tables_header_offset(self, mock_to_df):
        table1 = self.make_mock_table(col_count=3)
        table2 = self.make_mock_table(col_count=3)
        page = MagicMock()
        page.find_tables.return_value = [table1, table2]

        # simulate to_df_with_loc returning different dfs
        mock_to_df.side_effect = [
            pd.DataFrame([[1,2,3],[4,5,6]], columns=['A','B','C']),
            pd.DataFrame([[7,8,9],[10,11,12]], columns=['A','B','C'])
        ]
        table_setup = TableSetup(columns={'A':(True,), 'B':(True,), 'C':(True,)},
                                 row_offset=1, expected_num_tables=2)
        df, errors = extract_table(page, "key", table_setup)
        # concatenated data
        assert df.shape[0] == 4
        assert df.iloc[0,0] == 1
        assert df.iloc[2,0] == 7

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_ignore_columns_removed(self, mock_to_df):
        table = self.make_mock_table(col_count=3)
        page = MagicMock()
        page.find_tables.return_value = [table]

        mock_to_df.return_value = pd.DataFrame([[1,2,3],[4,5,6]], columns=['A','B','C'])
        table_setup = TableSetup(columns={'A':(False,), 'B':(True,), 'C':(True,)})
        df, _ = extract_table(page, "key", table_setup)
        # A column removed
        assert 'A' not in df.columns
        assert 'B' in df.columns

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_row_filtering_empty(self, mock_to_df):
        table = self.make_mock_table(col_count=2)
        page = MagicMock()
        page.find_tables.return_value = [table]

        # some empty rows
        mock_to_df.return_value = pd.DataFrame([
            [1,2],
            [pd.NA,''],
            [3,4]
        ], columns=['A','B'])
        table_setup = TableSetup(columns={'A':(True,), 'B':(True,)})
        df, _ = extract_table(page, "key", table_setup)
        # middle row removed
        assert df.shape[0] == 2

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.to_df_with_loc")
    def test_forward_fill_applied(self, mock_to_df):
        table = self.make_mock_table(col_count=2)
        page = MagicMock()
        page.find_tables.return_value = [table]

        # some placeholder for ffill
        mock_to_df.return_value = pd.DataFrame([
            ['X','keep'],
            ['ffill_val','keep']
        ], columns=['A','B'])
        table_setup = TableSetup(columns={'A':(True,'ffill_val'), 'B':(True,)})
        df, _ = extract_table(page, "key", table_setup)
        # ffill replaced pd.NA and filled
        assert df['A'].iloc[1] == 'X' or df['A'].iloc[1] != 'ffill_val'


class TestExtractText:

    def make_mock_page(self, text: str):
        """Helper to create a mock pymupdf.Page"""
        page = MagicMock()
        page.get_text.return_value = text
        return page

    def test_text_found_basic(self):
        page = self.make_mock_page("Hello World")
        table_setup = TableSetup(roi=None)
        df, errors = extract_text(page, "my_col", table_setup)

        # DataFrame returned correctly
        assert isinstance(df, pd.DataFrame)
        assert df.shape == (1,1)
        assert df.columns.tolist() == ["my_col"]
        assert df.iloc[0,0] == "Hello World"

        # errors list is empty
        assert errors == []

    def test_text_found_with_whitespace(self):
        # Should strip whitespace
        page = self.make_mock_page("   Some text with spaces   ")
        table_setup = TableSetup(roi=None)
        df, errors = extract_text(page, "col", table_setup)
        assert df.iloc[0,0] == "Some text with spaces"

    def test_text_missing_raises_value_error(self):
        # Empty string
        page = self.make_mock_page("")
        table_setup = TableSetup(roi=None)
        with pytest.raises(ValueError, match="No required text"):
            extract_text(page, "col", table_setup)

    def test_text_none_raises_value_error(self):
        # get_text returns None
        page = self.make_mock_page(None)
        table_setup = TableSetup(roi=None)
        with pytest.raises(ValueError, match="No required text"):
            extract_text(page, "col", table_setup)


class TestExtractTables:

    def make_mock_page(self):
        """Helper to create a mock pymupdf.Page"""
        page = MagicMock()
        return page

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_text")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_table")
    def test_single_text_table(self, mock_extract_table, mock_extract_text):
        page = self.make_mock_page()
        df_mock = pd.DataFrame([[1]], columns=["A"])
        mock_extract_text.return_value = (df_mock, [PageError("info", error_type="INFO")])

        table_setup = TableSetup(text_only=True)
        page_setup = PageSetup(tables={"txt": table_setup})

        res, errors = extract_tables(page, page_setup)

        assert "txt" in res
        assert res["txt"].equals(df_mock)
        assert len(errors) == 1
        mock_extract_text.assert_called_once()
        mock_extract_table.assert_not_called()

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_text")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_table")
    def test_single_table_normal(self, mock_extract_table, mock_extract_text):
        page = self.make_mock_page()
        df_mock = pd.DataFrame([[1,2]], columns=["A","B"])
        mock_extract_table.return_value = (df_mock, [])

        table_setup = TableSetup(text_only=False)
        page_setup = PageSetup(tables={"tbl": table_setup})

        res, errors = extract_tables(page, page_setup)

        assert "tbl" in res
        assert res["tbl"].equals(df_mock)
        assert errors == []
        mock_extract_table.assert_called_once()
        mock_extract_text.assert_not_called()

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_text")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_table")
    def test_multiple_tables_mixed(self, mock_extract_table, mock_extract_text):
        page = self.make_mock_page()

        df_text = pd.DataFrame([["text"]], columns=["TXT"])
        df_table = pd.DataFrame([[1,2]], columns=["A","B"])

        mock_extract_text.return_value = (df_text, [PageError("text_error", error_type="INFO")])
        mock_extract_table.return_value = (df_table, [PageError("table_error", error_type="WARNING")])

        page_setup = PageSetup(tables={
            "txt": TableSetup(text_only=True),
            "tbl": TableSetup(text_only=False)
        })

        res, errors = extract_tables(page, page_setup)

        # check all keys present
        assert set(res.keys()) == {"txt","tbl"}
        # dataframes match
        assert res["txt"].equals(df_text)
        assert res["tbl"].equals(df_table)
        # errors aggregated
        assert len(errors) == 2
        assert any(e.message=="text_error" for e in errors)
        assert any(e.message=="table_error" for e in errors)

        # call counts
        mock_extract_text.assert_called_once()
        mock_extract_table.assert_called_once()

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_text")
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_table")
    def test_no_tables(self, mock_extract_table, mock_extract_text):
        page = self.make_mock_page()
        page_setup = PageSetup(tables={})

        res, errors = extract_tables(page, page_setup)

        assert res == {}
        assert errors == []
        mock_extract_text.assert_not_called()
        mock_extract_table.assert_not_called()


class TestTableExtractor:

    def make_mock_page(self, number=None):
        page = MagicMock()
        page.number = number
        return page

    # -------------------------------
    # get_extractor tests
    # -------------------------------
    def test_get_extractor_known_types(self):
        assert TableExtractor.get_extractor(PageType.TERMINAL_DIAGRAM) == TableExtractor.extract_terminal_diagram
        assert TableExtractor.get_extractor(PageType.CABLE_DIAGRAM) == TableExtractor.extract_cable_diagram

    def test_get_extractor_unknown_type_returns_stub(self):
        class UnknownType: pass
        extractor = TableExtractor.get_extractor(UnknownType)
        assert extractor == TableExtractor.extract_main_stub

    # -------------------------------
    # extract method tests
    # -------------------------------
    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_tables")
    def test_extract_success(self, mock_extract_tables):
        page = self.make_mock_page(3)
        dfs_mock = {"main": pd.DataFrame([[1]])}
        errors_list = []
        mock_extract_tables.return_value = (dfs_mock, errors_list)

        # patch get_extractor to just return stub
        with patch.object(TableExtractor, 'get_extractor', return_value=TableExtractor.extract_main_stub):
            df, errors = TableExtractor.extract(page, PageType.CABLE_DIAGRAM, PageSetup(tables={}))

        assert isinstance(df, pd.DataFrame)
        assert df.equals(dfs_mock["main"])
        assert errors == []

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_tables")
    def test_extract_value_error_caught(self, mock_extract_tables):
        page = self.make_mock_page(1)
        # simulate extract_tables returning empty dict
        mock_extract_tables.return_value = ({}, [])

        # patch stub to raise ValueError
        with patch.object(TableExtractor, 'get_extractor', side_effect=ValueError("bad")):
            df, errors = TableExtractor.extract(page, PageType.CABLE_DIAGRAM, PageSetup(tables={}))

        assert df is None
        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.FAULT
        assert "bad" in errors[0].message

    @patch("indu_doc.plugins.eplan_pdfs.table_extractor.extract_tables")
    def test_extract_unknown_exception_caught(self, mock_extract_tables):
        page = self.make_mock_page(1)
        mock_extract_tables.return_value = ({"main": pd.DataFrame([[1]])}, [])

        with patch.object(TableExtractor, 'get_extractor', side_effect=RuntimeError("oops")):
            df, errors = TableExtractor.extract(page, PageType.CABLE_DIAGRAM, PageSetup(tables={}))

        assert df is None
        assert len(errors) == 1
        assert errors[0].error_type == ErrorType.UNKNOWN_ERROR
        assert "oops" in errors[0].message

    # -------------------------------
    # extract_main_stub tests
    # -------------------------------
    def test_extract_main_stub_success(self):
        dfs = {"main": pd.DataFrame([[1,2]])}
        df, errors = TableExtractor.extract_main_stub(dfs)
        assert df.equals(dfs["main"])
        assert errors == []

    def test_extract_main_stub_missing_main_raises(self):
        dfs = {"other": pd.DataFrame([[1]])}
        with pytest.raises(ValueError, match="Required table was not found: main"):
            TableExtractor.extract_main_stub(dfs)

    # -------------------------------
    # extract_cable_diagram tests
    # -------------------------------
    def test_extract_cable_diagram_basic(self):
        df = pd.DataFrame([
            ["Cable =A1", None, None, 1],
            ["Text", None, None, 2],
            ["Cable1", "Cable2", None, 3],
            ["Data1", "Data2", 1, 2],
            ["Data3", "Data4", 3, 4]
        ], columns=["col0", "col1", "col2", "col3"])
        dfs = {"main": df}

        result_df, errors = TableExtractor.extract_cable_diagram(dfs)
        assert isinstance(result_df, pd.DataFrame)
        assert errors == []
        assert "cable_tag" in result_df.columns

    def test_extract_cable_diagram_missing_main_raises(self):
        dfs = {"other": pd.DataFrame([[1]])}
        with pytest.raises(ValueError, match="Required table was not found: main"):
            TableExtractor.extract_cable_diagram(dfs)

    # -------------------------------
    # extract_terminal_diagram tests
    # -------------------------------
    def test_extract_terminal_diagram_basic(self):
        dfs = {
            "main": pd.DataFrame([
                    ["cable_pin_1", "SRC_A", "PIN_A1", "DST_B", "PIN_B1"],
                    ["cable_pin_2", "SRC_C", "PIN_C1", "DST_D", "PIN_D1"],
                ], 
                columns=["strip_pin", "src_tag", "src_pin", "dst_tag", "dst_pin"]),
            "r_cables": pd.DataFrame([{"cable_tag": "R1", "_loc": "locR"}]),
            "r_conn": pd.DataFrame([{"1": "red", "_loc": "locRconn1"}, {"": "", "_loc": "locRconn2"}]),
            "l_cables": pd.DataFrame([{"cable_tag": "L1", "_loc": "locL"}]),
            "l_conn": pd.DataFrame([{"1": "blue", "_loc": "locLconn1"}, {"1": "blue", "_loc": "locLconn2"}]),
            "strip_tag": pd.DataFrame([{"strip_tag": "StripA"}])
        }

        df, errors = TableExtractor.extract_terminal_diagram(dfs)
        assert isinstance(df, pd.DataFrame)
        assert errors == []
        # columns prefixed with _1 and _2 exist
        assert any(c.startswith("_1") for c in df.columns)
        assert any(c.startswith("_2") for c in df.columns)

    # -------------------------------
    # extract_terminal_diagram tests
    # -------------------------------
    def test_extract_terminal_all_required_columns_are_present(self):
        dfs = {
            "main": pd.DataFrame([
                    ["strip_pin", "SRC", "PIN_SRC", "DST", "PIN_DST", "loc"],
                ], 
                columns=["strip_pin", "src_tag", "src_pin", "dst_tag", "dst_pin", "_loc"]),
            "r_cables": pd.DataFrame([{"cable_tag": "R1", "_loc": "locR"}]),
            "r_conn": pd.DataFrame([{"1": "red", "_loc": "locRconn1"}]),
            "l_cables": pd.DataFrame([{"cable_tag": "L1", "_loc": "locL"}]),
            "l_conn": pd.DataFrame([{"1": "blue", "_loc": "locLconn1"}]),
            "strip_tag": pd.DataFrame([{"strip_tag": "Strip"}])
        }

        df, errors = TableExtractor.extract_terminal_diagram(dfs)
        print(df)
        assert isinstance(df, pd.DataFrame)
        assert df["_1src_tag"].iloc[0] == "SRC"
        assert df["_1dst_tag"].iloc[0] == "Strip"
        assert df["_1src_pin"].iloc[0] == "PIN_SRC"
        assert df["_1dst_pin"].iloc[0] == "strip_pin"
        assert df["_2src_tag"].iloc[0] == "Strip"
        assert df["_2dst_tag"].iloc[0] == "DST"
        assert df["_2src_pin"].iloc[0] == "strip_pin"
        assert df["_2dst_pin"].iloc[0] == "PIN_DST"
        assert df["_loc"].iloc[0] == "loc"
        assert errors == []
        # columns prefixed with _1 and _2 exist
        assert any(c.startswith("_1") for c in df.columns)
        assert any(c.startswith("_2") for c in df.columns)
