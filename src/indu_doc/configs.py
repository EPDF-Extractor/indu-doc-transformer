import json
from dataclasses import dataclass
from typing import OrderedDict, List


@dataclass
class LevelConfig:
    # Configuration for each aspect level
    Separator: str
    Aspect: str


class AspectsConfig:
    """
    Configuration class for aspect levels.

    Attributes:
        levels (OrderedDict[str, LevelConfig]): A mapping of aspect separators to their configuration, sorted by their order of priority as listed in the config.
    """

    def __init__(self, config: dict[str, LevelConfig]):
        self.levels = config

    def __getitem__(self, item: str) -> LevelConfig:
        return self.levels[item]

    @classmethod
    def init_from_file(cls, filepath) -> "AspectsConfig":
        """
            Extracts configuration from a JSON file and returns an OrderedDict
            where keys are the 'Separator' values and values are LevelConfig instances.
            We take levels in the ascending order we find them in the file or list. 
        Args:
            filepath (str): The path to the JSON configuration file.
        Returns:
            AspectsConfig: An instance of AspectsConfig containing the extracted configuration.
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
        config = json.loads(json_str).get("aspects", [])
        return cls.init_from_list(config)

    # @classmethod
    # def to_json_str(cls) -> str:
    #     json.dumps()

    @classmethod
    def init_from_list(cls, config_list: List[dict]) -> "AspectsConfig":
        """
        Initialize AspectsConfig directly from a list of dicts (same format as the JSON file).
        This avoids depending on an external file for defaults.
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
        ours = list(self.separators)
        # return all separators so that we only cover the seps > the lowest sep in others
        if not others:
            return ours
        lowest_pri_other = max(others, key=lambda sep: ours.index(sep))
        return [sep for sep in ours if ours.index(sep) <= ours.index(lowest_pri_other)]

    def to_list(self) -> List[LevelConfig]:
        """
        Converts the internal OrderedDict back to a list of LevelConfig objects.
        """
        return list(self.levels.values())

    @property
    def separators(self):
        """
        Returns the aspect separators defined in the configuration, sorted by 'Order'.
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
    {"Aspect": "Product Aspect", "Separator": "-"},
    {"Aspect": "Pins", "Separator": ":"},
    {"Aspect": "Subdivision", "Separator": "/"},
    {"Aspect": "Document", "Separator": "&"},
]
default_configs = AspectsConfig.init_from_list(__DEFAULT_CONFIG_LIST)


if __name__ == "__main__":
    config_dict = default_configs.levels
    print(config_dict)
    print(config_dict["="].Aspect)  # Should print "Functional"
    print(config_dict.keys())  # Should print the keys of the OrderedDict
