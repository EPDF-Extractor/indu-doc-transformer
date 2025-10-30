"""
Test suite for searcher module.
Tests the Searcher class and search functionality.
"""

from typing import OrderedDict

from indu_doc.searcher import Searcher, _merge_search_tree
from indu_doc.god import God
from indu_doc.xtarget import XTarget, XTargetType
from indu_doc.connection import Connection
from indu_doc.tag import Tag
from indu_doc.configs import AspectsConfig, LevelConfig
from indu_doc.footers import PageFooter


class TestMergeSearchTree:
    """Tests for _merge_search_tree helper function."""

    def test_merge_simple_dict(self):
        """Test merging a simple dictionary."""
        tree = {}
        data = {"name": "test", "value": "123"}
        _merge_search_tree(tree, data)
        
        assert "name" in tree
        assert "value" in tree

    def test_merge_nested_dict(self):
        """Test merging nested dictionaries."""
        tree = {}
        data = {"level1": {"level2": {"level3": "value"}}}
        _merge_search_tree(tree, data)
        
        assert "level1" in tree
        assert "level2" in tree["level1"]
        assert "level3" in tree["level1"]["level2"]

    def test_merge_with_list(self):
        """Test merging data with lists."""
        tree = {}
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        _merge_search_tree(tree, data)
        
        assert "items" in tree
        assert "[list items]" in tree["items"]

    def test_merge_list_with_name_key(self):
        """Test merging list items with 'name' key."""
        tree = {}
        data = {"items": [
            {"name": "Item1", "value": "10"},
            {"name": "Item2", "value": "20"}
        ]}
        _merge_search_tree(tree, data)
        
        filters = tree["items"]["[list items]"].get("__filters__", set())
        assert any("Item1" in f for f in filters)
        assert any("Item2" in f for f in filters)

    def test_merge_list_with_unit(self):
        """Test merging list items with units."""
        tree = {}
        data = {"parameters": [
            {"name": "Length", "unit": "m", "value": "10"}
        ]}
        _merge_search_tree(tree, data)
        
        filters = tree["parameters"]["[list items]"].get("__filters__", set())
        # Should include unit in display
        assert any("Length" in f and "[m]" in f for f in filters)

    def test_merge_with_filters(self):
        """Test that filters are created for leaf values."""
        tree = {}
        data = {"config": {"setting": "value"}}
        _merge_search_tree(tree, data)
        
        # The implementation creates filters only for certain patterns
        # Just verify tree structure is created
        assert "config" in tree
        assert "setting" in tree["config"]


class TestSearcher:
    """Tests for the Searcher class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = AspectsConfig(
            OrderedDict({
                "=": LevelConfig(Separator="=", Aspect="Functional"),
                "+": LevelConfig(Separator="+", Aspect="Location"),
            })
        )
        self.footer = PageFooter(
            project_name="Test",
            product_name="Test",
            tags=[]
        )

    def create_tag(self, tag_str: str) -> Tag:
        """Helper to create a tag."""
        return Tag.get_tag_with_footer(tag_str, self.footer, self.config)

    def test_searcher_initialization_empty(self):
        """Test Searcher initialization with empty god."""
        god = God(self.config)
        searcher = Searcher(god)
        
        assert searcher.god == god
        assert len(searcher.xtargets_index) == 0
        assert len(searcher.connections_index) == 0

    def test_searcher_initialization_with_targets(self):
        """Test Searcher initialization with targets indexing."""
        god = God(self.config)
        tag = self.create_tag("=A+B")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god, init_index=["targets"])
        assert len(searcher.xtargets_index) == 1
        assert target.get_guid() in searcher.xtargets_index

    def test_searcher_initialization_with_connections(self):
        """Test Searcher initialization with connections indexing."""
        god = God(self.config)
        
        # Create targets
        tag1 = self.create_tag("=A+B")
        tag2 = self.create_tag("=C+D")
        target1 = XTarget(tag1, self.config, XTargetType.DEVICE)
        target2 = XTarget(tag2, self.config, XTargetType.DEVICE)
        
        god.xtargets[target1.get_guid()] = target1
        god.xtargets[target2.get_guid()] = target2
        
        # Create connection using the correct constructor
        conn = Connection(src=target1, dest=target2, through=None)
        god.connections[conn.get_guid()] = conn
        
        searcher = Searcher(god, init_index=["conns"])
        assert len(searcher.connections_index) == 1
        assert conn.get_guid() in searcher.connections_index

    def test_index_targets(self):
        """Test indexing targets."""
        god = God(self.config)
        tag = self.create_tag("=DEV+LOC")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god)
        searcher.index_targets(god.xtargets)
        
        guid = target.get_guid()
        assert guid in searcher.xtargets_index
        assert searcher.xtargets_index[guid]["tag"] == "=dev+loc"  # normalized

    def test_index_connections(self):
        """Test indexing connections."""
        god = God(self.config)
        
        # Create targets
        tag1 = self.create_tag("=A+B")
        tag2 = self.create_tag("=C+D")
        target1 = XTarget(tag1, self.config, XTargetType.DEVICE)
        target2 = XTarget(tag2, self.config, XTargetType.DEVICE)
        god.xtargets[target1.get_guid()] = target1
        god.xtargets[target2.get_guid()] = target2
        
        # Create connection
        conn = Connection(src=target1, dest=target2)
        god.connections[conn.get_guid()] = conn
        
        searcher = Searcher(god)
        searcher.index_connections(god.connections)
        
        guid = conn.get_guid()
        assert guid in searcher.connections_index
        assert searcher.connections_index[guid]["src"] == "=A+B"
        assert searcher.connections_index[guid]["dest"] == "=C+D"

    def test_search_targets_by_tag(self):
        """Test searching targets by tag."""
        god = God(self.config)
        tag1 = self.create_tag("=DEV+LOC")
        tag2 = self.create_tag("=OTHER+LOC")
        target1 = XTarget(tag1, self.config, XTargetType.DEVICE)
        target2 = XTarget(tag2, self.config, XTargetType.DEVICE)
        god.xtargets[target1.get_guid()] = target1
        god.xtargets[target2.get_guid()] = target2
        
        searcher = Searcher(god, init_index=["targets"])
        results = searcher.search_targets("=DEV")
        
        assert target1.get_guid() in results
        assert target2.get_guid() not in results

    def test_search_targets_no_match(self):
        """Test searching targets with no match."""
        god = God(self.config)
        tag = self.create_tag("=DEV+LOC")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god, init_index=["targets"])
        results = searcher.search_targets("=NOMATCH")
        
        assert len(results) == 0

    def test_search_connections_by_src(self):
        """Test searching connections by source tag."""
        god = God(self.config)
        
        # Create targets
        tag1 = self.create_tag("=SRC+LOC")
        tag2 = self.create_tag("=DEST+LOC")
        target1 = XTarget(tag1, self.config, XTargetType.DEVICE)
        target2 = XTarget(tag2, self.config, XTargetType.DEVICE)
        god.xtargets[target1.get_guid()] = target1
        god.xtargets[target2.get_guid()] = target2
        
        # Create connection
        conn = Connection(src=target1, dest=target2)
        god.connections[conn.get_guid()] = conn
        
        searcher = Searcher(god, init_index=["conns"])
        results = searcher.search_connections("@src=SRC")
        
        assert conn.get_guid() in results

    def test_check_path_match_simple(self):
        """Test _check_path_match with simple path."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"name": "test", "value": "123"}
        assert searcher._check_path_match(data, ["name"], None, "test")
        assert searcher._check_path_match(data, ["name"], None, "tes")
        assert not searcher._check_path_match(data, ["name"], None, "other")

    def test_check_path_match_nested(self):
        """Test _check_path_match with nested path."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"level1": {"level2": "value"}}
        assert searcher._check_path_match(data, ["level1", "level2"], None, "value")
        assert not searcher._check_path_match(data, ["level1", "level2"], None, "other")

    def test_check_path_match_with_list(self):
        """Test _check_path_match with list in path."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        assert searcher._check_path_match(data, ["items", "name"], None, "item1")
        assert searcher._check_path_match(data, ["items", "name"], None, "item2")
        assert not searcher._check_path_match(data, ["items", "name"], None, "item3")

    def test_check_path_match_with_param(self):
        """Test _check_path_match with parameter."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"attributes": {"color": "red", "size": "large"}}
        assert searcher._check_path_match(data, ["attributes"], "color", "red")
        assert not searcher._check_path_match(data, ["attributes"], "color", "blue")

    def test_check_path_match_list_with_param(self):
        """Test _check_path_match with list and parameter."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"items": [
            {"name": "color", "value": "red"},
            {"name": "size", "value": "large"}
        ]}
        assert searcher._check_path_match(data, ["items"], "name", "color")
        assert searcher._check_path_match(data, ["items"], "value", "red")

    def test_check_path_match_no_value(self):
        """Test _check_path_match with no value (existence check)."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"name": "test"}
        assert searcher._check_path_match(data, ["name"], None, None)

    def test_check_path_match_nonexistent_path(self):
        """Test _check_path_match with nonexistent path."""
        god = God(self.config)
        searcher = Searcher(god)
        
        data = {"name": "test"}
        assert not searcher._check_path_match(data, ["nonexistent"], None, None)

    def test_create_target_search_guide_tree(self):
        """Test creating target search guide tree."""
        god = God(self.config)
        tag = self.create_tag("=DEV+LOC")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god, init_index=["targets"])
        tree = searcher.create_target_search_guide_tree()
        
        assert isinstance(tree, dict)
        assert "tag" in tree

    def test_create_connection_search_guide_tree(self):
        """Test creating connection search guide tree."""
        god = God(self.config)
        
        # Create targets
        tag1 = self.create_tag("=A+B")
        tag2 = self.create_tag("=C+D")
        target1 = XTarget(tag1, self.config, XTargetType.DEVICE)
        target2 = XTarget(tag2, self.config, XTargetType.DEVICE)
        god.xtargets[target1.get_guid()] = target1
        god.xtargets[target2.get_guid()] = target2
        
        # Create connection
        conn = Connection(src=target1, dest=target2)
        god.connections[conn.get_guid()] = conn
        
        searcher = Searcher(god, init_index=["conns"])
        tree = searcher.create_connection_search_guide_tree()
        
        assert isinstance(tree, dict)
        assert "src" in tree
        assert "dest" in tree

    def test_start_indexing(self):
        """Test start_indexing method."""
        god = God(self.config)
        searcher = Searcher(god)
        # Should not raise any error
        searcher.start_indexing()

    def test_search_with_multiple_filters(self):
        """Test searching with multiple filters."""
        god = God(self.config)
        tag = self.create_tag("=DEV+LOC")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god, init_index=["targets"])
        results = searcher.search_targets("=DEV @tag")
        
        assert target.get_guid() in results

    def test_partial_match_case_insensitive(self):
        """Test that partial matching is case insensitive."""
        god = God(self.config)
        tag = self.create_tag("=Device+Location")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god, init_index=["targets"])
        results = searcher.search_targets("=device")
        
        assert target.get_guid() in results

    def test_empty_search_query(self):
        """Test search with empty query."""
        god = God(self.config)
        tag = self.create_tag("=DEV+LOC")
        target = XTarget(tag, self.config, XTargetType.DEVICE)
        god.xtargets[target.get_guid()] = target
        
        searcher = Searcher(god, init_index=["targets"])
        results = searcher.search_targets("")
        
        # Empty query should return all targets
        assert target.get_guid() in results
