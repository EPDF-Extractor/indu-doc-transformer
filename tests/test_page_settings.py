import json
import os
import pytest
from unittest.mock import mock_open, patch

from indu_doc.common_page_utils import PageType
from indu_doc.page_settings import TableSetup, PageSetup, PageSettings


class TestPageSettings:
    """Comprehensive tests for PageSettings, TableSetup, and PageSetup classes."""

    # --- Fixtures ---
    @pytest.fixture
    def table_setup(self):
        return TableSetup(
            key_columns={"id": "identifier"},
            description="Test table setup",
            roi=(10, 20, 30, 40),
            text_only=False,
            lines=[((0, 0), (1, 1))],
            columns={"col1": (True,), "col2": (False, "x")},
            overlap_test_roi=None,
            expected_num_tables=2,
            on_many_join=True,
            on_many_no_header=False,
            row_offset=1,
        )

    @pytest.fixture
    def page_setup(self, table_setup):
        return PageSetup(
            tables={"main": table_setup},
            description="Main page setup",
            search_name="CablePlanPage",
        )

    @pytest.fixture
    def page_settings_dict(self, page_setup):
        return {PageType.CABLE_PLAN: page_setup}

    @pytest.fixture
    def temp_filename(self, tmp_path):
        return tmp_path / "settings.json"

    # --- Basic behavior ---
    def test_set_get_contains(self, temp_filename, page_settings_dict):
        ps = PageSettings(str(temp_filename), pages_setup=page_settings_dict)
        assert PageType.CABLE_PLAN in ps
        assert ps[PageType.CABLE_PLAN].search_name == "CablePlanPage"

        # Setting new page setup
        new_setup = PageSetup(tables={}, description="New", search_name="NewPage")
        ps[PageType.TERMINAL_DIAGRAM] = new_setup
        assert ps[PageType.TERMINAL_DIAGRAM].description == "New"

    # --- to_enum ---
    def test_to_enum_returns_correct_mapping(self, temp_filename, page_settings_dict):
        ps = PageSettings(str(temp_filename), pages_setup=page_settings_dict)
        enum_map = ps.to_enum()
        assert enum_map == {PageType.CABLE_PLAN: "CablePlanPage"}

    # --- to_json and from_json roundtrip ---
    def test_to_json_and_from_json_roundtrip(self, temp_filename, page_settings_dict):
        ps = PageSettings(str(temp_filename), pages_setup=page_settings_dict)
        json_str = ps.to_json()

        ps2 = PageSettings(str(temp_filename))
        ps2.from_json(json_str)

        assert PageType.CABLE_PLAN in ps2.pages_setup
        setup = ps2.pages_setup[PageType.CABLE_PLAN]
        assert setup.description == "Main page setup"
        assert "main" in setup.tables
        assert setup.tables["main"].roi == (10, 20, 30, 40)

    # --- from_json error handling ---
    def test_from_json_handles_invalid_json(self, temp_filename):
        ps = PageSettings(str(temp_filename))
        with patch("json.loads", side_effect=ValueError("invalid json")):
            ps.from_json("not valid json")
        assert ps.pages_setup == {}

    # --- save() writes expected content ---
    def test_save_writes_json_to_file(self, temp_filename, page_settings_dict):
        ps = PageSettings(str(temp_filename), pages_setup=page_settings_dict)
        content = ps.to_json()

        with patch("builtins.open", mock_open()) as m:
            ps.save()
            m.assert_called_once_with(str(temp_filename), "w", encoding="utf-8")
            handle = m()
            handle.write.assert_called_once_with(content)

    # --- load() reads and populates data ---
    def test_load_reads_from_file(self, temp_filename, page_settings_dict):
        ps = PageSettings(str(temp_filename), pages_setup=page_settings_dict)
        json_str = ps.to_json()

        with patch("builtins.open", mock_open(read_data=json_str)) as m:
            ps2 = PageSettings(str(temp_filename))
            m.assert_called_once_with(str(temp_filename), "a+", encoding="utf-8")
            assert PageType.CABLE_PLAN in ps2.pages_setup
            assert ps2.pages_setup[PageType.CABLE_PLAN].search_name == "CablePlanPage"

    # --- load() with empty file ---
    def test_load_with_empty_file(self, temp_filename):
        with patch("builtins.open", mock_open(read_data="")):
            ps = PageSettings(str(temp_filename))
            assert ps.pages_setup == {}

    # --- init_from_file() ---
    def test_init_from_file_creates_instance(self, temp_filename):
        with patch.object(PageSettings, "load", return_value=None):
            ps = PageSettings.init_from_file(str(temp_filename))
            assert isinstance(ps, PageSettings)
            assert ps.filename == str(temp_filename)

    # --- to_json produces valid JSON ---
    def test_to_json_serialization_structure(self, temp_filename, page_settings_dict):
        ps = PageSettings(str(temp_filename), pages_setup=page_settings_dict)
        json_str = ps.to_json()
        data = json.loads(json_str)
        key = next(iter(data.keys()))
        assert key == PageType.CABLE_PLAN.name
        assert "tables" in data[key]
        assert "description" in data[key]
        assert "search_name" in data[key]
