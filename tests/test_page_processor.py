import pytest
import pandas as pd
from itertools import product
from unittest.mock import MagicMock, patch

from indu_doc.plugins.eplan_pdfs.page_processor import PageProcessor
from indu_doc.plugins.eplan_pdfs.common_page_utils import PageError, ErrorType, PageInfo, PageType
from indu_doc.attributes import Attribute, AttributeType, PDFLocationAttribute
from indu_doc.xtarget import XTargetType

class TestPageProcessorRun:
    """Tests for PageProcessor.run() behavior."""

    @pytest.fixture
    def mock_god(self):
        god = MagicMock()
        god.create_error = MagicMock()
        god.create_attribute = MagicMock()
        god.create_connection_with_link = MagicMock()
        god.create_connection = MagicMock()
        god.create_xtarget = MagicMock()
        god.create_aspect = MagicMock()
        return god

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.to_enum.return_value = {"dummy": "type_map"}
        settings.__contains__.return_value = True
        settings.__getitem__.return_value = MagicMock()
        return settings

    @pytest.fixture
    def page_proc(self, mock_god, mock_settings):
        return PageProcessor(mock_god, mock_settings)

    def make_mock_page(self):
        page = MagicMock()
        page.number = 0
        return page

    @patch("indu_doc.plugins.eplan_pdfs.page_processor.detect_page_type", return_value=None)
    def test_run_page_type_not_detected(self, mock_detect, page_proc):
        page = self.make_mock_page()

        result = page_proc.run(page)

        assert result is None
        assert mock_detect.called
        # check logger and error list path executed
        page_proc.god.add_errors.assert_not_called()

    @patch("indu_doc.plugins.eplan_pdfs.page_processor.detect_page_type", return_value=PageType.CABLE_PLAN)
    @patch("indu_doc.plugins.eplan_pdfs.page_processor.extract_footer", return_value=None)
    def test_run_no_footer(self, mock_footer, mock_detect, page_proc):
        page = self.make_mock_page()

        result = page_proc.run(page)

        assert result is None
        mock_footer.assert_called_once()
        page_proc.god.add_errors.assert_not_called()

    @patch("indu_doc.plugins.eplan_pdfs.page_processor.detect_page_type", return_value=PageType.CABLE_PLAN)
    @patch("indu_doc.plugins.eplan_pdfs.page_processor.extract_footer", return_value="footer")
    @patch("indu_doc.plugins.eplan_pdfs.page_processor.TableExtractor.extract", return_value=(None, [PageError("err")]))
    def test_run_no_table_found(self, mock_extract, mock_footer, mock_detect, page_proc):
        page = self.make_mock_page()

        result = page_proc.run(page)

        assert result is None
        page_proc.god.add_errors.assert_called_once()
        assert isinstance(page_proc.god.add_errors.call_args[0][1][0], PageError)

    @patch("indu_doc.plugins.eplan_pdfs.page_processor.detect_page_type", return_value=PageType.CABLE_PLAN)
    @patch("indu_doc.plugins.eplan_pdfs.page_processor.extract_footer", return_value="footer")
    @patch("indu_doc.plugins.eplan_pdfs.page_processor.TableExtractor.extract", return_value=(pd.DataFrame({"a": [1]}), []))
    def test_run_successful_process_called(self, mock_extract, mock_footer, mock_detect, page_proc):
        page = self.make_mock_page()
        with patch.object(page_proc, "process") as mock_proc:
            page_proc.run(page)
            mock_proc.assert_called_once()
            args, _ = mock_proc.call_args
            assert isinstance(args[0], pd.DataFrame)
            assert isinstance(args[1], PageInfo)

    def test_process_handles_valueerror(self, page_proc):
        df = pd.DataFrame({"tag": ["A"]})
        page_info = MagicMock()
        page_info.page_type = PageType.CABLE_OVERVIEW

        with patch.object(page_proc, "process_cable_overview", side_effect=ValueError("bad value")):
            page_proc.process(df, page_info)
            page_proc.god.create_error.assert_called_once()
            call = page_proc.god.create_error.call_args[0]
            assert "bad value" in call[1]

    def test_process_handles_generic_exception(self, page_proc):
        df = pd.DataFrame({"tag": ["A"]})
        page_info = MagicMock()
        page_info.page_type = PageType.CABLE_OVERVIEW

        with patch.object(page_proc, "process_cable_overview", side_effect=RuntimeError("boom")):
            page_proc.process(df, page_info)
            page_proc.god.create_error.assert_called_once()
            call = page_proc.god.create_error.call_args[0]
            assert "boom" in call[1]

    def test_process_invalid_handler(self, page_proc):
        df = pd.DataFrame({"tag": ["A"]})
        page_info = MagicMock()
        page_info.page_type = "NON_EXISTENT_TYPE"

        with pytest.raises(AssertionError):
            page_proc.process(df, page_info)

    def test_process_empty_dataframe_returns_early(self, page_proc):
        df = pd.DataFrame()
        page_info = MagicMock()
        page_info.page_type = PageType.CABLE_PLAN
        result = page_proc.process(df, page_info)
        assert result is None


class TestProcessConnectionList:
    @pytest.fixture
    def processor(self):
        """Create an instance of PageProcessor with a mocked 'god' and 'logger'."""
        proc = PageProcessor.__new__(PageProcessor)
        proc.god = MagicMock()
        proc.logger = MagicMock()
        return proc

    @pytest.fixture
    def page_info(self):
        """Stub page info."""
        return MagicMock(page=MagicMock(number=5))

    def test_skips_empty_tags_creates_warning(self, processor, page_info):
        """Should skip rows with empty tags and log a warning."""
        df = pd.DataFrame([
            {"src_pin_tag": "", "dst_pin_tag": "X"},
            {"src_pin_tag": "A", "dst_pin_tag": ""},
        ])
        processor.god.create_error = MagicMock()
        processor.god.create_connection_with_link = MagicMock()

        processor.process_connection_list(df, page_info)

        assert processor.god.create_connection_with_link.call_count == 0
        assert processor.god.create_error.call_count == 2
        for call in processor.god.create_error.call_args_list:
            assert call.kwargs["error_type"] == ErrorType.WARNING

    def test_creates_connection_with_basic_attributes(self, processor, page_info):
        """Should create a connection with simple attributes."""
        df = pd.DataFrame([
            {
                "src_pin_tag": "SRC",
                "dst_pin_tag": "DST",
                "name": "Conn1",
                "color": "blue",
                "length": "5m"
            }
        ])
        processor.god.create_attribute = MagicMock(side_effect=lambda *a, **k: ("attr", a, k))
        processor.god.create_connection_with_link = MagicMock()

        processor.process_connection_list(df, page_info)

        processor.god.create_connection_with_link.assert_called_once()
        args = processor.god.create_connection_with_link.call_args.args
        assert args[1] == "SRC"
        assert args[2] == "DST"
        attrs = args[4]
        assert len(attrs) == 2  # color + length
        assert all(a[1][1] in ("color", "length") for a in attrs)

    def test_adds_location_attribute_when_present(self, processor, page_info):
        """Should add PDF_LOCATION attribute when '_loc' exists."""
        df = pd.DataFrame([
            {
                "src_pin_tag": "SRC",
                "dst_pin_tag": "DST",
                "name": "Conn2",
                "_loc": "bbox(10,10,20,20)"
            }
        ])
        processor.god.create_attribute = MagicMock(side_effect=lambda *a, **k: ("attr", a, k))
        processor.god.create_connection_with_link = MagicMock()

        processor.process_connection_list(df, page_info)

        args = processor.god.create_connection_with_link.call_args.args
        attrs = args[4]
        assert any("PDF_LOCATION" in str(a[1][0]) for a in attrs)

    def test_ignores_internal_columns_starting_with_underscore(self, processor, page_info):
        """Should not treat columns starting with '_' as attributes."""
        df = pd.DataFrame([
            {"src_pin_tag": "A", "dst_pin_tag": "B", "_internal": "IGNORE"}
        ])
        processor.god.create_attribute = MagicMock()
        processor.god.create_connection_with_link = MagicMock()

        processor.process_connection_list(df, page_info)

        # no create_attribute for internal columns
        assert not any(
            "IGNORE" in str(c) for c in processor.god.create_attribute.call_args_list
        )

    def test_handles_multiple_rows_mixed_valid_invalid(self, processor, page_info):
        """Should handle mix of valid and invalid rows."""
        df = pd.DataFrame([
            {"src_pin_tag": "", "dst_pin_tag": ""},  # invalid
            {"src_pin_tag": "A", "dst_pin_tag": "B"},  # valid
        ])
        processor.god.create_attribute = MagicMock(return_value="attr")
        processor.god.create_connection_with_link = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_connection_list(df, page_info)

        processor.god.create_connection_with_link.assert_called_once()
        processor.god.create_error.assert_called_once()


class TestProcessDeviceTagList:

    @pytest.fixture
    def processor(self):
        mock_god = MagicMock()
        mock_settings = MagicMock()  # if settings is required, mock minimally
        return PageProcessor(mock_god, mock_settings)

    @pytest.fixture
    def page_info(self):
        mock_page_info = MagicMock(spec=PageInfo)
        mock_page_info.page = MagicMock(number=5)  # required for PDF_LOCATION
        return mock_page_info

    def test_creates_xtarget_for_valid_tag(self, processor, page_info):
        """Should create an xtarget for a valid tag with simple attributes"""
        df = pd.DataFrame([
            {"tag": "DEVICE1", "color": "red", "type": "sensor"}
        ])
        processor.god.create_attribute = MagicMock()
        processor.god.create_xtarget = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_device_tag_list(df, page_info)

        # Should create attributes for 'color' and 'type'
        assert processor.god.create_attribute.call_count == 2
        # Should call create_xtarget once
        processor.god.create_xtarget.assert_called_once()
        # Should not call create_error
        assert processor.god.create_error.call_count == 0

    def test_skips_empty_tag_creates_warning(self, processor, page_info):
        """Should skip rows with empty tag and create a warning"""
        df = pd.DataFrame([
            {"tag": ""},
            {"tag": "   "}  # whitespace only
        ])
        processor.god.create_attribute = MagicMock()
        processor.god.create_xtarget = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_device_tag_list(df, page_info)

        # Should not create attributes or xtarget
        assert processor.god.create_attribute.call_count == 0
        assert processor.god.create_xtarget.call_count == 0
        # Should create two warnings
        assert processor.god.create_error.call_count == 2
        for call in processor.god.create_error.call_args_list:
            assert call.kwargs["error_type"] == ErrorType.WARNING

    def test_includes_loc_metadata_as_attribute(self, processor, page_info):
        """Should include _loc as PDF_LOCATION attribute"""
        df = pd.DataFrame([
            {"tag": "DEVICE2", "_loc": (1, 2, 3, 4)}
        ])
        processor.god.create_attribute = MagicMock()
        processor.god.create_xtarget = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_device_tag_list(df, page_info)

        # Should call create_attribute twice: one for PDF_LOCATION, none for other
        attrs_calls = processor.god.create_attribute.call_args_list
        assert any(call.args[0] == AttributeType.PDF_LOCATION for call in attrs_calls)
        # Should call xtarget once
        processor.god.create_xtarget.assert_called_once()
        # No errors
        assert processor.god.create_error.call_count == 0

    def test_combined_attributes(self, processor, page_info):
        """Should combine simple attributes and _loc metadata"""
        df = pd.DataFrame([
            {"tag": "DEVICE3", "color": "blue", "_loc": (5, 6, 7, 8)}
        ])
        processor.god.create_attribute = MagicMock()
        processor.god.create_xtarget = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_device_tag_list(df, page_info)

        # Expect two attributes: one SIMPLE, one PDF_LOCATION
        assert processor.god.create_attribute.call_count == 2
        # Check that xtarget includes tuple of attributes
        args, kwargs = processor.god.create_xtarget.call_args
        attr_tuple = kwargs["attributes"] if "attributes" in kwargs else args[3]
        assert len(attr_tuple) == 2


class TestProcessCableOverview:

    @pytest.fixture
    def processor(self):
        """Create a mock PageProcessor with a fake 'god' object."""
        mock_god = MagicMock()
        processor = PageProcessor.__new__(PageProcessor)
        processor.god = mock_god
        return processor

    @pytest.fixture
    def page_info(self):
        """Create a mock PageInfo with a .page attribute."""
        mock_page_info = MagicMock()
        mock_page_info.page = MagicMock(number=11)  # required for PDF_LOCATION
        return mock_page_info

    def test_creates_connection_for_valid_row(self, processor, page_info):
        """Should create a connection when tag, src_tag, and dst_tag are present."""
        df = pd.DataFrame([
            {"cable_tag": "C1", "src_tag": "A", "dst_tag": "B", "color": "red"}
        ])

        def make_attr(type_, name, value):
            m = MagicMock()
            m.type = type_
            m.name = name
            m.value = value
            return m

        processor.god.create_attribute = MagicMock(side_effect=make_attr)
        processor.god.create_connection = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_cable_overview(df, page_info)

        # Connection should be created
        processor.god.create_connection.assert_called_once()
        args, kwargs = processor.god.create_connection.call_args
        assert args[0] == "C1"
        assert args[1] == "A"
        assert args[2] == "B"

        # Attributes should include SIMPLE attribute for color
        attrs = args[4]
        assert any(a.type == AttributeType.SIMPLE and a.name == "color" for a in attrs)

        # No errors should be created
        processor.god.create_error.assert_not_called()

    def test_skips_row_with_empty_cable_tag(self, processor, page_info):
        """Should skip row if cable_tag is empty and create a warning."""
        df = pd.DataFrame([
            {"cable_tag": "", "src_tag": "A", "dst_tag": "B"}
        ])

        processor.god.create_error = MagicMock()
        processor.god.create_connection = MagicMock()
        processor.god.create_attribute = MagicMock()

        processor.process_cable_overview(df, page_info)

        # Connection should not be created
        processor.god.create_connection.assert_not_called()
        # Error should be created with warning type
        processor.god.create_error.assert_called_once()
        args, kwargs = processor.god.create_error.call_args
        assert kwargs["error_type"] == ErrorType.WARNING

    def test_skips_row_with_empty_src_and_dst(self, processor, page_info):
        """Should skip row if both src_tag and dst_tag are empty and cable_tag is present."""
        df = pd.DataFrame([
            {"cable_tag": "C1", "src_tag": "", "dst_tag": ""}
        ])

        processor.god.create_error = MagicMock()
        processor.god.create_connection = MagicMock()
        processor.god.create_attribute = MagicMock()

        processor.process_cable_overview(df, page_info)

        processor.god.create_connection.assert_not_called()
        processor.god.create_error.assert_called_once()
        args, kwargs = processor.god.create_error.call_args
        assert kwargs["error_type"] == ErrorType.WARNING

    def test_creates_pdf_location_attribute_if_present(self, processor, page_info):
        """Should include PDF_LOCATION attribute if '_loc' column exists."""
        df = pd.DataFrame([
            {"cable_tag": "C1", "src_tag": "A", "dst_tag": "B", "_loc": (1, 2, 3, 4)}
        ])

        processor.god.create_attribute = MagicMock(
            side_effect=lambda *a, **kw: MagicMock(spec=Attribute, type=a[0], name=a[1], value=a[2])
        )
        processor.god.create_connection = MagicMock()
        processor.god.create_error = MagicMock()

        processor.process_cable_overview(df, page_info)

        # Connection should be created
        processor.god.create_connection.assert_called_once()
        # Attributes should include PDF_LOCATION
        attrs = processor.god.create_connection.call_args[0][4]
        assert any(a.type == AttributeType.PDF_LOCATION for a in attrs)


class TestProcessTopology:
    """Comprehensive tests for PageProcessor.process_topology"""

    @pytest.fixture
    def processor(self):
        """Creates a PageProcessor with a mocked 'god' and logger."""
        processor = PageProcessor.__new__(PageProcessor)
        processor.god = MagicMock()
        processor.logger = MagicMock()
        return processor

    @pytest.fixture
    def page_info(self):
        """Creates a fake PageInfo with page attribute."""
        mock_page_info = MagicMock()
        mock_page_info.page.number = 42
        return mock_page_info

    def test_skips_row_with_missing_required_fields(self, processor, page_info):
        """Should log warning and skip rows missing required fields."""
        df = pd.DataFrame([
            {"designation": "", "src_tags": "SRC", "dst_tags": "DST", "route": "R"},
            {"designation": "D", "src_tags": "", "dst_tags": "DST", "route": "R"},
            {"designation": "D", "src_tags": "SRC", "dst_tags": "", "route": "R"},
            {"designation": "D", "src_tags": "SRC", "dst_tags": "DST", "route": ""},
        ])

        processor.process_topology(df, page_info)

        # All 4 rows skipped
        assert processor.god.create_connection.call_count == 0
        assert processor.god.create_error.call_count == 4
        for call in processor.god.create_error.call_args_list:
            args = call.args
            assert args[0] == page_info
            assert "skipped" in args[1]
            assert call.kwargs["error_type"] == ErrorType.WARNING

    def test_creates_connections_for_valid_row(self, processor, page_info):
        """Should create connections for a valid topology row."""
        df = pd.DataFrame([
            {"designation": "NET1", "src_tags": "SRC1", "dst_tags": "DST1", "route": "R1"}
        ])
        processor.god.create_attribute = MagicMock(
            side_effect=lambda *a, **kw: MagicMock(spec=Attribute, type=a[0], name=a[1], value=a[2])
        )

        processor.process_topology(df, page_info)

        processor.god.create_error.assert_not_called()
        processor.god.create_connection.assert_called_once()

        call_args = processor.god.create_connection.call_args[0]
        assert call_args[0] == "NET1"
        assert call_args[1] == "SRC1"
        assert call_args[2] == "DST1"
        attrs = call_args[4]
        assert any(a.type == AttributeType.ROUTING_TRACKS for a in attrs)

    def test_includes_additional_simple_attributes(self, processor, page_info):
        """Should include additional non-reserved columns as simple attributes."""
        df = pd.DataFrame([
            {"designation": "NET", "src_tags": "S", "dst_tags": "D", "route": "R", "color": "red"}
        ])

        fake_attr = MagicMock(type=AttributeType.SIMPLE)
        processor.god.create_attribute.side_effect = lambda t, n, v: fake_attr

        processor.process_topology(df, page_info)

        # color should be added as attribute
        attrs = processor.god.create_connection.call_args[0][4]
        assert any(a.type == AttributeType.SIMPLE for a in attrs)
        processor.god.create_attribute.assert_any_call(AttributeType.SIMPLE, "color", "red")

    def test_includes_pdf_location_if_present(self, processor, page_info):
        """Should include PDF_LOCATION attribute if '_loc' exists."""
        df = pd.DataFrame([
            {
                "designation": "NET",
                "src_tags": "S",
                "dst_tags": "D",
                "route": "R",
                "_loc": (10, 20, 30, 40)
            }
        ])

        def fake_attr(attr_type, name, value):
            mock = MagicMock()
            mock.type = attr_type
            mock.name = name
            mock.value = value
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_topology(df, page_info)

        attrs = processor.god.create_connection.call_args[0][4]
        assert any(a.type == AttributeType.PDF_LOCATION for a in attrs)
        assert any(a.type == AttributeType.ROUTING_TRACKS for a in attrs)

    def test_creates_multiple_connections_for_multiple_tags(self, processor, page_info):
        """Should create all combinations of src_tags × dst_tags."""
        df = pd.DataFrame([
            {
                "designation": "NETX",
                "src_tags": "A1;A2",
                "dst_tags": "B1;B2;B3",
                "route": "R"
            }
        ])
        processor.god.create_attribute.return_value = MagicMock(type=AttributeType.SIMPLE)
        processor.process_topology(df, page_info)

        expected_combos = list(product(["A1", "A2"], ["B1", "B2", "B3"]))
        assert processor.god.create_connection.call_count == len(expected_combos)

        called_pairs = [(c.args[1], c.args[2]) for c in processor.god.create_connection.call_args_list]
        assert set(called_pairs) == set(expected_combos)


class TestProcessWiresPartList:
    """Comprehensive tests for PageProcessor.process_wires_part_list"""

    @pytest.fixture
    def processor(self):
        """Creates a PageProcessor mock with a fake god and logger."""
        processor = PageProcessor.__new__(PageProcessor)
        processor.god = MagicMock()
        processor.logger = MagicMock()
        return processor

    @pytest.fixture
    def page_info(self):
        """Creates a fake PageInfo with 'page' attribute."""
        mock_page_info = MagicMock()
        mock_page_info.page.number = 42
        return mock_page_info

    def test_skips_rows_with_empty_tags_and_logs_warning(self, processor, page_info):
        """Should skip rows missing src or dst and log a warning."""
        df = pd.DataFrame([
            {"src_pin_tag": "", "dst_pin_tag": "D", "route": "R"},
            {"src_pin_tag": "S", "dst_pin_tag": "", "route": "R"}
        ])

        processor.process_wires_part_list(df, page_info)

        # both skipped
        assert processor.god.create_connection_with_link.call_count == 0
        assert processor.god.create_error.call_count == 2

        for call in processor.god.create_error.call_args_list:
            args = call.args
            assert args[0] == page_info
            assert "skipped" in args[1]
            assert call.kwargs["error_type"] == ErrorType.WARNING

    def test_creates_connection_with_valid_tags(self, processor, page_info):
        """Should create a connection when both tags are present."""
        df = pd.DataFrame([
            {"src_pin_tag": "S1", "dst_pin_tag": "D1", "route": ""}
        ])

        processor.god.create_attribute.return_value = MagicMock(type=AttributeType.SIMPLE)
        processor.process_wires_part_list(df, page_info)

        processor.god.create_error.assert_not_called()
        processor.god.create_connection_with_link.assert_called_once()

        call_args = processor.god.create_connection_with_link.call_args[0]
        assert call_args[1] == "S1"
        assert call_args[2] == "D1"

    def test_adds_simple_attributes_for_additional_columns(self, processor, page_info):
        """Should add SIMPLE attributes for non-reserved columns."""
        df = pd.DataFrame([
            {"src_pin_tag": "S", "dst_pin_tag": "D", "route": "R", "color": "red", "type": "signal"}
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_wires_part_list(df, page_info)

        attrs = processor.god.create_connection_with_link.call_args[0][4]
        assert any(a.name == "color" for a in attrs)
        assert any(a.name == "type" for a in attrs)

    def test_adds_pdf_location_if_loc_column_exists(self, processor, page_info):
        """Should add PDF_LOCATION attribute if '_loc' column is present."""
        df = pd.DataFrame([
            {"src_pin_tag": "S", "dst_pin_tag": "D", "route": "R", "_loc": (1, 2, 3, 4)}
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_wires_part_list(df, page_info)

        attrs = processor.god.create_connection_with_link.call_args[0][4]
        assert any(a.type == AttributeType.PDF_LOCATION for a in attrs)

    def test_adds_routing_tracks_attribute_if_route_present(self, processor, page_info):
        """Should add ROUTING_TRACKS attribute if 'route' is not empty."""
        df = pd.DataFrame([
            {"src_pin_tag": "S", "dst_pin_tag": "D", "route": "PATH123"}
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_wires_part_list(df, page_info)

        attrs = processor.god.create_connection_with_link.call_args[0][4]
        assert any(a.type == AttributeType.ROUTING_TRACKS for a in attrs)
        assert any(a.value == "PATH123" for a in attrs)

    def test_no_route_skips_adding_routing_attribute(self, processor, page_info):
        """Should not add ROUTING_TRACKS if route is empty."""
        df = pd.DataFrame([
            {"src_pin_tag": "S", "dst_pin_tag": "D", "route": ""}
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_wires_part_list(df, page_info)

        attrs = processor.god.create_connection_with_link.call_args[0][4]
        assert not any(a.type == AttributeType.ROUTING_TRACKS for a in attrs)


class TestProcessCableDiagram:
    """Comprehensive tests for PageProcessor.process_cable_diagram"""

    @pytest.fixture
    def processor(self):
        """Creates PageProcessor instance with mocked dependencies."""
        processor = PageProcessor.__new__(PageProcessor)
        processor.god = MagicMock()
        processor.logger = MagicMock()
        return processor

    @pytest.fixture
    def page_info(self):
        """Creates a fake PageInfo with 'page' attribute."""
        page_info = MagicMock()
        page_info.page.number = 7
        return page_info

    def test_skips_row_with_all_empty_fields_and_logs_warning(self, processor, page_info):
        """Should skip a row when all src/dst/pins are empty and log a warning."""
        df = pd.DataFrame([
            {"cable_tag": "CB1", "src_tag": "", "src_pin": "", "dst_tag": "", "dst_pin": ""}
        ])

        processor.process_cable_diagram(df, page_info)

        # No connection should be made
        processor.god.create_connection_with_link.assert_not_called()
        # Error should be logged and warning issued
        processor.god.create_error.assert_called_once()
        msg = processor.god.create_error.call_args[0][1]
        assert "skipped" in msg
        assert "CB1" in msg

    def test_creates_connection_for_valid_single_row(self, processor, page_info):
        """Should create one connection for valid tags and pins."""
        df = pd.DataFrame([
            {
                "cable_tag": "CB10",
                "src_tag": "SRC1",
                "src_pin": "P1",
                "dst_tag": "DST1",
                "dst_pin": "P2",
                "route": "R1"
            }
        ])

        processor.god.create_attribute.return_value = MagicMock(type=AttributeType.SIMPLE)
        processor.process_cable_diagram(df, page_info)

        processor.god.create_error.assert_not_called()
        processor.god.create_connection_with_link.assert_called_once()

        args = processor.god.create_connection_with_link.call_args[0]
        assert args[0] == "CB10"
        assert args[1] == "SRC1:P1"
        assert args[2] == "DST1:P2"

    def test_creates_simple_attributes_for_additional_columns(self, processor, page_info):
        """Should create SIMPLE attributes for all non-reserved columns."""
        df = pd.DataFrame([
            {
                "cable_tag": "CB2",
                "src_tag": "A",
                "src_pin": "1",
                "dst_tag": "B",
                "dst_pin": "2",
                "color": "red",
                "size": "XL"
            }
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_cable_diagram(df, page_info)

        attrs = processor.god.create_connection_with_link.call_args[0][4]
        assert any(a.name == "color" for a in attrs)
        assert any(a.name == "size" for a in attrs)
        assert all(a.type == AttributeType.SIMPLE or a.type == AttributeType.PDF_LOCATION for a in attrs)

    def test_adds_pdf_location_if_loc_column_present(self, processor, page_info):
        """Should add PDF_LOCATION attribute when '_loc' column exists."""
        df = pd.DataFrame([
            {
                "cable_tag": "CB3",
                "src_tag": "A",
                "src_pin": "1",
                "dst_tag": "B",
                "dst_pin": "2",
                "_loc": (100, 200, 300, 400)
            }
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_cable_diagram(df, page_info)

        attrs = processor.god.create_connection_with_link.call_args[0][4]
        pdf_attrs = [a for a in attrs if a.type == AttributeType.PDF_LOCATION]
        assert len(pdf_attrs) == 1
        assert pdf_attrs[0].value == (page_info.page.number, (100, 200, 300, 400))

    def test_creates_multiple_connections_for_semicolon_separated_tags(self, processor, page_info):
        """Should create connections for all src/dst tag-pin combinations."""
        df = pd.DataFrame([
            {
                "cable_tag": "CB_MULTI1;CB_MULTI2",
                "src_tag": "S1;S2",
                "src_pin": "P1;P2",
                "dst_tag": "D1;D2",
                "dst_pin": "Q1;Q2"
            }
        ])

        processor.god.create_attribute.return_value = MagicMock()
        processor.process_cable_diagram(df, page_info)

        # 2 src × 2 dst = 4 combinations expected
        assert processor.god.create_connection_with_link.call_count == 4

        all_calls = [call.args for call in processor.god.create_connection_with_link.call_args_list]
        assert any("S1:P1" in c for _, c, *_ in all_calls)
        assert any("S2:P2" in c for _, c, *_ in all_calls)
        assert any("D1:Q1" in d for _, _, d, *_ in all_calls)
        assert any("D2:Q2" in d for _, _, d, *_ in all_calls)

    def test_ignores_empty_other_columns_and_still_creates_connection(self, processor, page_info):
        """Should ignore empty extra columns but still create a connection."""
        df = pd.DataFrame([
            {
                "cable_tag": "CB_EMPTY",
                "src_tag": "SRC",
                "src_pin": "1",
                "dst_tag": "DST",
                "dst_pin": "2",
                "extra": ""
            }
        ])

        processor.god.create_attribute.return_value = MagicMock()
        processor.process_cable_diagram(df, page_info)

        processor.god.create_attribute.assert_not_called()  # extra column ignored
        processor.god.create_connection_with_link.assert_called_once()


class TestProcessPlcDiagram:
    """Comprehensive tests for PageProcessor.process_plc_diagram."""

    @pytest.fixture
    def processor(self):
        """Return a PageProcessor instance with mocked dependencies."""
        processor = PageProcessor.__new__(PageProcessor)
        processor.god = MagicMock()
        processor.logger = MagicMock()
        return processor

    @pytest.fixture
    def page_info(self):
        """Fake PageInfo with 'page' attribute."""
        page_info = MagicMock()
        page_info.page.number = 42
        return page_info

    def test_skips_row_with_empty_tag_and_logs_warning(self, processor, page_info):
        """Should skip row if tag is empty and log a warning."""
        df = pd.DataFrame([
            {"tag": "", "plc_addr": "DB1.DBX0.0"}
        ])

        processor.process_plc_diagram(df, page_info)

        # Verify warning path
        processor.god.create_xtarget.assert_not_called()
        processor.god.create_error.assert_called_once()
        msg = processor.god.create_error.call_args[0][1]
        assert "skipped" in msg and "empty" in msg

    def test_skips_row_with_empty_plc_addr_and_logs_warning(self, processor, page_info):
        """Should skip row if plc_addr is empty and log a warning."""
        df = pd.DataFrame([
            {"tag": "PLC_TAG", "plc_addr": ""}
        ])

        processor.process_plc_diagram(df, page_info)

        processor.god.create_xtarget.assert_not_called()
        processor.god.create_error.assert_called_once()
        msg = processor.god.create_error.call_args[0][1]
        assert "empty PLC diagram info" in msg

    def test_creates_xtarget_with_valid_data(self, processor, page_info):
        """Should create xtarget when both tag and plc_addr are provided."""
        df = pd.DataFrame([
            {"tag": "MOTOR1", "plc_addr": "DB1.DBX0.1"}
        ])

        attr_mock = MagicMock()
        attr_mock.type = AttributeType.PLC_ADDRESS
        processor.god.create_attribute.return_value = attr_mock

        processor.process_plc_diagram(df, page_info)

        processor.god.create_error.assert_not_called()
        processor.god.create_xtarget.assert_called_once()

        args = processor.god.create_xtarget.call_args[0]
        assert args[0] == "MOTOR1"
        assert args[1] == page_info
        assert args[2] == XTargetType.DEVICE
        attrs = args[3]
        assert any(a.type == AttributeType.PLC_ADDRESS for a in attrs)

    def test_includes_meta_information_in_plc_attribute(self, processor, page_info):
        """Should include additional non-empty columns as meta dict."""
        df = pd.DataFrame([
            {
                "tag": "VALVE_A",
                "plc_addr": "DB2.DBX5.0",
                "description": "Main valve",
                "color": "blue"
            }
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_plc_diagram(df, page_info)

        plc_attr = processor.god.create_attribute.call_args_list[0][0]
        assert plc_attr[0] == AttributeType.PLC_ADDRESS
        assert plc_attr[1] == "DB2.DBX5.0"
        meta_dict = plc_attr[2]
        assert meta_dict == {"description": "Main valve", "color": "blue"}

    def test_adds_pdf_location_attribute_if_loc_column_present(self, processor, page_info):
        """Should add PDF_LOCATION attribute when '_loc' column exists."""
        df = pd.DataFrame([
            {
                "tag": "SENSOR_B",
                "plc_addr": "DB3.DBX10.0",
                "_loc": (10, 20, 30, 40)
            }
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_plc_diagram(df, page_info)

        attrs = processor.god.create_xtarget.call_args[0][3]
        pdf_attrs = [a for a in attrs if a.type == AttributeType.PDF_LOCATION]
        assert len(pdf_attrs) == 1
        assert pdf_attrs[0].value == (page_info.page.number, (10, 20, 30, 40))

    def test_ignores_empty_meta_columns(self, processor, page_info):
        """Should ignore empty or whitespace-only meta fields."""
        df = pd.DataFrame([
            {
                "tag": "CTRL_BOX",
                "plc_addr": "DB10.DBX1.0",
                "comment": "   ",   # ignored
                "empty_col": ""     # ignored
            }
        ])

        processor.god.create_attribute.return_value = MagicMock()
        processor.process_plc_diagram(df, page_info)

        # Only PLC_ADDRESS attribute should be created
        calls = processor.god.create_attribute.call_args_list
        plc_attr_call = calls[0][0]
        assert plc_attr_call[0] == AttributeType.PLC_ADDRESS
        processor.god.create_xtarget.assert_called_once()


class TestProcessStructureIdentifierOverview:
    """Comprehensive tests for PageProcessor.process_structure_identifier_overview."""

    @pytest.fixture
    def processor(self):
        """Return a PageProcessor instance with mocked god and logger."""
        processor = PageProcessor.__new__(PageProcessor)
        processor.god = MagicMock()
        processor.logger = MagicMock()
        return processor

    @pytest.fixture
    def page_info(self):
        """Mocked PageInfo with 'page' property."""
        page_info = MagicMock()
        page_info.page.number = 7
        return page_info

    def test_creates_aspect_for_valid_tag_and_attributes(self, processor, page_info):
        """Should create aspect with simple attributes for valid tag."""
        df = pd.DataFrame([
            {"tag": "SECTION_A", "floor": "1", "zone": "north"}
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_structure_identifier_overview(df, page_info)

        # Should create one aspect
        processor.god.create_aspect.assert_called_once()
        args = processor.god.create_aspect.call_args[0]
        assert args[0] == "SECTION_A"
        assert args[1] == page_info
        attributes = args[2]
        # Two SIMPLE attributes should exist
        assert all(a.type == AttributeType.SIMPLE for a in attributes)
        names = [a.name for a in attributes]
        assert "floor" in names and "zone" in names


    def test_adds_pdf_location_attribute_if_loc_present(self, processor, page_info):
        """Should include PDF_LOCATION attribute when '_loc' column exists."""
        df = pd.DataFrame([
            {"tag": "STRUCT_1", "_loc": (10, 20, 30, 40)}
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_structure_identifier_overview(df, page_info)

        attrs = processor.god.create_aspect.call_args[0][2]
        pdf_attrs = [a for a in attrs if a.type == AttributeType.PDF_LOCATION]
        assert len(pdf_attrs) == 1
        assert pdf_attrs[0].value == (page_info.page.number, (10, 20, 30, 40))

    def test_ignores_empty_or_whitespace_values(self, processor, page_info):
        """Should ignore empty or whitespace-only secondary attributes."""
        df = pd.DataFrame([
            {
                "tag": "STRUCT_2",
                "desc": "   ",  # ignored
                "info": "",     # ignored
                "valid": "ok"
            }
        ])

        def fake_attr(t, n, v):
            mock = MagicMock()
            mock.type = t
            mock.name = n
            mock.value = v
            return mock

        processor.god.create_attribute.side_effect = fake_attr
        processor.process_structure_identifier_overview(df, page_info)

        attrs = processor.god.create_aspect.call_args[0][2]
        # Only 'valid' should remain
        assert len(attrs) == 1
        assert attrs[0].name == "valid"

    def test_handles_multiple_rows(self, processor, page_info):
        """Should process all rows independently and create aspects for each."""
        df = pd.DataFrame([
            {"tag": "A", "level": "1"},
            {"tag": "B", "level": "2"},
        ])

        processor.god.create_attribute.return_value = MagicMock()
        processor.process_structure_identifier_overview(df, page_info)

        # Two rows => two aspect creations
        assert processor.god.create_aspect.call_count == 2
        called_tags = [call.args[0] for call in processor.god.create_aspect.call_args_list]
        assert called_tags == ["A", "B"]


    def test_creates_aspect_with_no_secondary_attributes(self, processor, page_info):
        """Should still create aspect if only 'tag' is present."""
        df = pd.DataFrame([
            {"tag": "ONLY_TAG"}
        ])

        processor.god.create_attribute.return_value = MagicMock()
        processor.process_structure_identifier_overview(df, page_info)

        processor.god.create_aspect.assert_called_once()
        tag, _, attributes = processor.god.create_aspect.call_args[0]
        assert tag == "ONLY_TAG"
        assert attributes == tuple()  # no attributes


class TestProcessTerminalDiagram:
    """Comprehensive tests for PageProcessor.process_terminal_diagram."""

    @pytest.fixture
    def processor(self):
        """Return PageProcessor instance with mocked process_cable_diagram."""
        processor = PageProcessor.__new__(PageProcessor)
        processor.process_cable_diagram = MagicMock()
        return processor

    @pytest.fixture
    def page_info(self):
        """Mocked PageInfo object with 'page' property."""
        page_info = MagicMock()
        page_info.page.number = 42
        return page_info

    def test_processes_both_left_and_right_prefixed_columns(self, processor, page_info):
        """Should correctly strip _1/_2 prefixes and call process_cable_diagram twice."""
        df = pd.DataFrame([
            {
                "_1cable_tag": "L1",
                "_1src_tag": "SRC_L",
                "_2cable_tag": "R1",
                "_2src_tag": "SRC_R",
                "common": "shared"
            }
        ])

        processor.process_terminal_diagram(df, page_info)

        # Two calls to process_cable_diagram
        assert processor.process_cable_diagram.call_count == 2

        # Extract both DataFrames
        left_df, right_df = (
            processor.process_cable_diagram.call_args_list[0][0][0],
            processor.process_cable_diagram.call_args_list[1][0][0],
        )

        # Left DataFrame should contain stripped column names
        assert set(left_df.columns) == {"cable_tag", "src_tag", "common"}
        assert left_df.iloc[0]["cable_tag"] == "L1"
        assert left_df.iloc[0]["src_tag"] == "SRC_L"
        assert left_df.iloc[0]["common"] == "shared"

        # Right DataFrame should also contain stripped names
        assert set(right_df.columns) == {"cable_tag", "src_tag", "common"}
        assert right_df.iloc[0]["cable_tag"] == "R1"
        assert right_df.iloc[0]["src_tag"] == "SRC_R"
        assert right_df.iloc[0]["common"] == "shared"

        # Both should be called with the same page_info
        assert all(call.args[1] == page_info for call in processor.process_cable_diagram.call_args_list)

    def test_handles_only_left_columns(self, processor, page_info):
        """Should work even when only _1-prefixed columns exist."""
        df = pd.DataFrame([
            {"_1cable_tag": "L_ONLY", "_1src_tag": "SRC_L_ONLY"}
        ])

        processor.process_terminal_diagram(df, page_info)

        # Two calls (l_df and r_df)
        assert processor.process_cable_diagram.call_count == 2
        l_df = processor.process_cable_diagram.call_args_list[0][0][0]
        r_df = processor.process_cable_diagram.call_args_list[1][0][0]

        # l_df should contain stripped columns
        assert list(l_df.columns) == ["cable_tag", "src_tag"]
        assert l_df.iloc[0]["cable_tag"] == "L_ONLY"

        # r_df should have same columns but NaNs for right (since missing)
        assert list(r_df.columns) == list()

    def test_handles_only_right_columns(self, processor, page_info):
        """Should work even when only _2-prefixed columns exist."""
        df = pd.DataFrame([
            {"_2cable_tag": "R_ONLY", "_2dst_tag": "DST_R_ONLY"}
        ])

        processor.process_terminal_diagram(df, page_info)

        assert processor.process_cable_diagram.call_count == 2
        l_df = processor.process_cable_diagram.call_args_list[0][0][0]
        r_df = processor.process_cable_diagram.call_args_list[1][0][0]

        # Left should contain no columns (no _1 columns)
        assert set(l_df.columns) == set()

        # Right should have proper values
        assert r_df.iloc[0]["cable_tag"] == "R_ONLY"
        assert r_df.iloc[0]["dst_tag"] == "DST_R_ONLY"

    def test_handles_no_prefixed_columns(self, processor, page_info):
        """Should still call process_cable_diagram twice with base columns only."""
        df = pd.DataFrame([
            {"cable_tag": "BASE", "src_tag": "SRC"}
        ])

        processor.process_terminal_diagram(df, page_info)

        # Called twice
        assert processor.process_cable_diagram.call_count == 2
        for call in processor.process_cable_diagram.call_args_list:
            df_arg = call[0][0]
            # Both left and right DF identical
            assert df_arg.equals(df)

    def test_prefix_stripping_works_for_multiple_levels(self, processor, page_info):
        """Ensure that both _1 and _2 prefixes are correctly removed regardless of column order."""
        df = pd.DataFrame([
            {"_2cable_tag": "R2", "_1cable_tag": "L2", "_1src_tag": "SRC_L2", "extra": "value"}
        ])

        processor.process_terminal_diagram(df, page_info)

        left_df, right_df = (
            processor.process_cable_diagram.call_args_list[0][0][0],
            processor.process_cable_diagram.call_args_list[1][0][0],
        )

        assert "cable_tag" in left_df.columns
        assert "cable_tag" in right_df.columns
        assert "extra" in left_df.columns
        assert "extra" in right_df.columns
