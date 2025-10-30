"""
Tests for the configs module.

This module tests AspectsConfig and LevelConfig classes,
including initialization, properties, and configuration management.
"""

import pytest
import json
import tempfile
import os
from typing import OrderedDict

from indu_doc.configs import (
    LevelConfig,
    AspectsConfig,
    default_configs,
)


class TestLevelConfig:
    """Test LevelConfig dataclass."""

    def test_create_level_config(self):
        """Test creating a LevelConfig."""
        config = LevelConfig(Separator="=", Aspect="Functional")

        assert config.Separator == "="
        assert config.Aspect == "Functional"

    def test_level_config_with_different_values(self):
        """Test LevelConfig with various values."""
        configs = [
            LevelConfig(Separator="+", Aspect="Location"),
            LevelConfig(Separator="-", Aspect="Product"),
            LevelConfig(Separator=":", Aspect="Pins"),
        ]

        assert configs[0].Separator == "+"
        assert configs[1].Aspect == "Product"
        assert len(configs) == 3


class TestAspectsConfig:
    """Test AspectsConfig class."""

    def test_create_aspects_config(self):
        """Test creating AspectsConfig with OrderedDict."""
        config = OrderedDict({
            "=": LevelConfig(Separator="=", Aspect="Functional"),
            "+": LevelConfig(Separator="+", Aspect="Location"),
        })

        aspects_config = AspectsConfig(config)

        assert aspects_config.levels == config
        assert len(aspects_config.levels) == 2

    def test_getitem(self):
        """Test accessing levels by key."""
        config = OrderedDict({
            "=": LevelConfig(Separator="=", Aspect="Functional"),
            "+": LevelConfig(Separator="+", Aspect="Location"),
        })
        aspects_config = AspectsConfig(config)

        level = aspects_config["="]

        assert level.Aspect == "Functional"
        assert level.Separator == "="

    def test_getitem_missing_key(self):
        """Test accessing non-existent key raises KeyError."""
        config = OrderedDict({
            "=": LevelConfig(Separator="=", Aspect="Functional"),
        })
        aspects_config = AspectsConfig(config)

        with pytest.raises(KeyError):
            _ = aspects_config["?"]

    def test_init_from_list(self):
        """Test initializing from list."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ]

        aspects_config = AspectsConfig.init_from_list(config_list)

        assert len(aspects_config.levels) == 3
        assert "=" in aspects_config.levels
        assert "+" in aspects_config.levels
        assert "-" in aspects_config.levels

    def test_init_from_list_order_preserved(self):
        """Test that order is preserved when initializing from list."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ]

        aspects_config = AspectsConfig.init_from_list(config_list)

        separators = list(aspects_config.separators)
        assert separators == ["=", "+", "-"]

    def test_init_from_file(self):
        """Test initializing from JSON file."""
        # Create a temporary JSON file
        config_data = {
            "aspects": [
                {"Aspect": "Functional", "Separator": "="},
                {"Aspect": "Location", "Separator": "+"},
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            aspects_config = AspectsConfig.init_from_file(temp_path)

            assert len(aspects_config.levels) == 2
            assert aspects_config["="].Aspect == "Functional"
            assert aspects_config["+"].Aspect == "Location"
        finally:
            os.unlink(temp_path)

    def test_init_from_file_empty_aspects(self):
        """Test initializing from file with empty aspects."""
        config_data = {"aspects": []}

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            aspects_config = AspectsConfig.init_from_file(temp_path)

            assert len(aspects_config.levels) == 0
        finally:
            os.unlink(temp_path)

    def test_to_list(self):
        """Test converting config to list."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
        ]

        aspects_config = AspectsConfig.init_from_list(config_list)
        result_list = aspects_config.to_list()

        assert len(result_list) == 2
        assert all(isinstance(item, LevelConfig) for item in result_list)
        assert result_list[0].Aspect == "Functional"
        assert result_list[1].Aspect == "Location"

    def test_separators_property(self):
        """Test separators property."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ]

        aspects_config = AspectsConfig.init_from_list(config_list)
        separators = list(aspects_config.separators)

        assert separators == ["=", "+", "-"]

    def test_aspects_property(self):
        """Test aspects property."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ]

        aspects_config = AspectsConfig.init_from_list(config_list)
        aspects = aspects_config.aspects

        assert aspects == ["Functional", "Location", "Product"]

    def test_equality_same_configs(self):
        """Test equality with same configurations."""
        config1 = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
        ])
        config2 = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
        ])

        assert config1 == config2

    def test_equality_different_configs(self):
        """Test equality with different configurations."""
        config1 = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
        ])
        config2 = AspectsConfig.init_from_list([
            {"Aspect": "Location", "Separator": "+"},
        ])

        assert config1 != config2

    def test_equality_with_non_aspects_config(self):
        """Test equality with non-AspectsConfig object."""
        config = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
        ])

        assert config != "not a config"
        assert config != 123
        assert config != None

    def test_repr(self):
        """Test string representation."""
        config = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
        ])

        repr_str = repr(config)

        assert "AspectsConfig" in repr_str
        assert "levels=" in repr_str

    def test_empty_config(self):
        """Test creating empty configuration."""
        empty_config = AspectsConfig(OrderedDict())

        assert len(empty_config.levels) == 0
        assert list(empty_config.separators) == []
        assert empty_config.aspects == []


class TestDefaultConfigs:
    """Test default configuration."""

    def test_default_configs_exists(self):
        """Test that default_configs is defined."""
        assert default_configs is not None
        assert isinstance(default_configs, AspectsConfig)

    def test_default_configs_has_expected_separators(self):
        """Test default configuration has expected separators."""
        separators = list(default_configs.separators)

        # Should contain standard separators
        assert "=" in separators
        assert "+" in separators
        assert "-" in separators
        assert ":" in separators

    def test_default_configs_functional_aspect(self):
        """Test default config has functional aspect."""
        level = default_configs["="]

        assert level.Aspect == "Functional"
        assert level.Separator == "="

    def test_default_configs_location_aspect(self):
        """Test default config has location aspect."""
        level = default_configs["+"]

        assert level.Aspect == "Location"
        assert level.Separator == "+"

    def test_default_configs_product_aspect(self):
        """Test default config has product aspect."""
        level = default_configs["-"]

        assert level.Aspect == "Product"
        assert level.Separator == "-"

    def test_default_configs_pins_aspect(self):
        """Test default config has pins aspect."""
        level = default_configs[":"]

        assert level.Aspect == "Pin"
        assert level.Separator == ":"

    def test_default_configs_order(self):
        """Test that default configs maintain order."""
        separators = list(default_configs.separators)

        # Order should be preserved as defined
        assert separators.index("=") < separators.index("+")
        assert separators.index("+") < separators.index("-")


class TestAspectsConfigIntegration:
    """Integration tests for AspectsConfig."""

    def test_roundtrip_list_conversion(self):
        """Test converting to list and back preserves data."""
        original = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
        ])

        as_list = original.to_list()

        # Reconstruct from list
        config_dicts = [
            {"Aspect": level.Aspect, "Separator": level.Separator}
            for level in as_list
        ]
        reconstructed = AspectsConfig.init_from_list(config_dicts)

        assert original == reconstructed

    def test_file_and_list_init_equivalence(self):
        """Test that file and list initialization produce same result."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
        ]

        from_list = AspectsConfig.init_from_list(config_list)

        # Create temporary file
        config_data = {"aspects": config_list}
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            from_file = AspectsConfig.init_from_file(temp_path)

            assert from_list == from_file
        finally:
            os.unlink(temp_path)

    def test_complex_configuration(self):
        """Test with complex multi-level configuration."""
        config_list = [
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
            {"Aspect": "Pins", "Separator": ":"},
            {"Aspect": "Subdivision", "Separator": "/"},
            {"Aspect": "Document", "Separator": "&"},
        ]

        config = AspectsConfig.init_from_list(config_list)

        assert len(config.levels) == 6
        assert len(config.aspects) == 6
        assert list(config.separators) == ["=", "+", "-", ":", "/", "&"]

    def test_special_characters_in_aspect_names(self):
        """Test aspects with special characters."""
        config_list = [
            {"Aspect": "Test-Aspect", "Separator": "="},
            {"Aspect": "Aspect (1)", "Separator": "+"},
            {"Aspect": "Aspect/2", "Separator": "-"},
        ]

        config = AspectsConfig.init_from_list(config_list)

        assert config["="].Aspect == "Test-Aspect"
        assert config["+"].Aspect == "Aspect (1)"
        assert config["-"].Aspect == "Aspect/2"


class TestAspectsConfigAdditional:
    """Additional tests for AspectsConfig."""

    def test_from_json_str(self):
        """Test creating AspectsConfig from JSON string."""
        json_str = json.dumps({
            "aspects": [
                {"Aspect": "Functional", "Separator": "="},
                {"Aspect": "Location", "Separator": "+"},
            ]
        })

        config = AspectsConfig.from_json_str(json_str)

        assert len(config.levels) == 2
        assert config["="].Aspect == "Functional"
        assert config["+"].Aspect == "Location"

    def test_from_json_str_empty_aspects(self):
        """Test creating AspectsConfig from JSON with empty aspects."""
        json_str = json.dumps({"aspects": []})

        config = AspectsConfig.from_json_str(json_str)

        assert len(config.levels) == 0

    def test_separator_ge_with_empty(self):
        """Test separator_ge with empty list."""
        config = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ])

        result = config.separator_ge([])

        # Should return all separators when others is empty
        assert result == ["=", "+", "-"]

    def test_separator_ge_with_separator(self):
        """Test separator_ge with specific separator."""
        config = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ])

        result = config.separator_ge(["+"])

        # Should return separators >= "+" in priority
        assert result == ["=", "+"]

    def test_separator_ge_with_multiple(self):
        """Test separator_ge with multiple separators."""
        config = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
            {"Aspect": "Product", "Separator": "-"},
        ])

        result = config.separator_ge(["-", "+"])

        # Should return separators >= lowest priority (which is "-" as it has max index)
        assert result == ["=", "+", "-"]

    def test_get_db_representation(self):
        """Test converting config to database representation."""
        config = AspectsConfig.init_from_list([
            {"Aspect": "Functional", "Separator": "="},
            {"Aspect": "Location", "Separator": "+"},
        ])

        db_repr = config.get_db_representation()

        assert len(db_repr) == 2
        assert db_repr[0]["Separator"] == "="
        assert db_repr[0]["Aspect"] == "Functional"
        assert db_repr[1]["Separator"] == "+"
        assert db_repr[1]["Aspect"] == "Location"
