"""
Configuration management for aspect levels and separators.

This module provides classes for managing aspect configuration, which defines
how hierarchical tags are parsed and interpreted. The configuration specifies
the separators used in tags and their priority order.
"""

import json
from dataclasses import dataclass
from typing import List


@dataclass
class LevelConfig:
    """
    Configuration for a single aspect level.
    
    :param Separator: The separator character for this level (e.g., "+", "-", "=")
    :type Separator: str
    :param Aspect: The name/description of this aspect level
    :type Aspect: str
    """
    # Configuration for each aspect level
    Separator: str
    Aspect: str


class AspectsConfig:
    """
    Configuration class for aspect levels.
    
    Manages the configuration of aspect separators and their priority order,
    which determines how tags are parsed into hierarchical components.
    
    :param config: Mapping of separators to their configurations
    :type config: dict[str, LevelConfig]
    
    :ivar levels: Mapping of aspect separators to their configuration, sorted by priority
    """

    def __init__(self, config: dict[str, LevelConfig]):
        """
        Initialize AspectsConfig.
        
        :param config: Dictionary mapping separators to LevelConfig objects
        :type config: dict[str, LevelConfig]
        """
        self.levels = config

    def __getitem__(self, item: str) -> LevelConfig:
        """
        Get level configuration by separator.
        
        :param item: The separator character
        :type item: str
        :return: The level configuration
        :rtype: LevelConfig
        """
        return self.levels[item]

    @classmethod
    def init_from_file(cls, filepath) -> "AspectsConfig":
        """
        Extract configuration from a JSON file.
        
        Reads aspect configuration from a JSON file and returns an AspectsConfig
        instance where keys are separator values and values are LevelConfig instances.
        Levels are ordered as they appear in the file.
        
        :param filepath: Path to the JSON configuration file
        :type filepath: str
        :return: New AspectsConfig instance
        :rtype: AspectsConfig
        """
        with open(filepath, "r", encoding="utf-8") as f:
            config = json.load(f).get("aspects", [])
        entries_with_order = {}
        i = 1  # start order from 1
        for item in config:
            order = i
            i += 1
            entries_with_order[order] = LevelConfig(**item)

        ret = dict()
        for _, level_config in entries_with_order.items():
            ret[level_config.Separator] = level_config
        return AspectsConfig(ret)
    
    @classmethod
    def from_json_str(cls, json_str: str):
        """
        Create AspectsConfig from a JSON string.
        
        :param json_str: JSON string containing aspect configuration
        :type json_str: str
        :return: New AspectsConfig instance
        :rtype: AspectsConfig
        """
        config = json.loads(json_str).get("aspects", [])
        return cls.init_from_list(config)

    # @classmethod
    # def to_json_str(cls) -> str:
    #     json.dumps()

    @classmethod
    def init_from_list(cls, config_list: List[dict]) -> "AspectsConfig":
        """
        Initialize AspectsConfig directly from a list of dictionaries.
        
        This avoids depending on an external file for defaults. The list
        should contain dictionaries with the same format as the JSON file.
        
        :param config_list: List of configuration dictionaries
        :type config_list: List[dict]
        :return: New AspectsConfig instance
        :rtype: AspectsConfig
        """
        entries_with_order = {}
        order = 1
        for item in config_list:
            entries_with_order[order] = LevelConfig(**item)
            order += 1

        ret = dict()
        for _, level_config in entries_with_order.items():
            ret[level_config.Separator] = level_config
        return AspectsConfig(ret)

    def separator_ge(self, others) -> list[str]:
        """
        Get separators with priority greater than or equal to the lowest in others.
        
        Returns all separators that cover levels up to and including the lowest
        priority separator found in the 'others' collection.
        
        :param others: Collection of separator characters
        :return: List of separators with sufficient priority
        :rtype: list[str]
        """
        ours = list(self.separators)
        # return all separators so that we only cover the seps > the lowest sep in others
        if not others:
            return ours
        lowest_pri_other = max(others, key=lambda sep: ours.index(sep))
        return [sep for sep in ours if ours.index(sep) <= ours.index(lowest_pri_other)]

    def to_list(self) -> List[LevelConfig]:
        """
        Convert the internal configuration to a list of LevelConfig objects.
        
        :return: List of level configurations
        :rtype: List[LevelConfig]
        """
        return list(self.levels.values())

    @property
    def separators(self):
        """
        Get the aspect separators defined in the configuration.
        
        Returns separators sorted by their priority order.
        
        :return: Keys representing separator characters
        :rtype: dict_keys
        """
        return self.levels.keys()

    @property
    def aspects(self):
        """
        Returns the aspect names defined in the configuration, sorted by 'Order'.
        """
        return [level.Aspect for level in self.levels.values()]

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, AspectsConfig):
            return False
        return self.levels == value.levels

    def get_db_representation(self) -> List[dict]:
        """
        Converts the configuration to a list of dictionaries for database storage.
        Each dictionary corresponds to a LevelConfig.
        """
        return [ {"Separator": level.Separator, "Aspect": level.Aspect} for level in self.levels.values() ]
    
    def __repr__(self) -> str:
        return f"AspectsConfig(levels={self.levels})"


# Default configuration embedded directly to avoid depending on an external file.
# Format: same as the former JSON file (list of dicts with Aspect, Separator, Order).
__DEFAULT_CONFIG_LIST = [
    {"Aspect": "Functional", "Separator": "="},
    {"Aspect": "Location", "Separator": "+"},
    {"Aspect": "Product", "Separator": "-"},
    {"Aspect": "Pin", "Separator": ":"},
    {"Aspect": "Subdivision", "Separator": "/"},
    {"Aspect": "Document", "Separator": "&"},
]
default_configs = AspectsConfig.init_from_list(__DEFAULT_CONFIG_LIST)


if __name__ == "__main__":
    config_dict = default_configs.levels
    print(config_dict)
    print(config_dict["="].Aspect)  # Should print "Functional"
    print(config_dict.keys())  # Should print the keys of the OrderedDict
