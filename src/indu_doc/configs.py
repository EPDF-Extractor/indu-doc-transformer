import json
from dataclasses import dataclass
from typing import OrderedDict


@dataclass
class LevelConfig:
    Order: int
    Separator: str
    Aspect: str


class AspectsConfig:
    """
    Configuration class for aspect levels.

    Attributes:
        levels (OrderedDict[str, LevelConfig]): A mapping of aspect separators to their configuration, sorted by 'Order' in ascending order.
    """

    def __init__(self, config: OrderedDict[str, LevelConfig]):
        self.levels = config

    def __getitem__(self, item: str) -> LevelConfig:
        return self.levels[item]

    @classmethod
    def init_from_file(cls, filepath) -> "AspectsConfig":
        """
            Extracts configuration from a JSON file and returns an OrderedDict
            where keys are the 'Separator' values and values are LevelConfig instances.

        Args:
            filepath (str): The path to the JSON configuration file.
        Returns:
            AspectsConfig: An instance of AspectsConfig containing the extracted configuration.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            config = json.load(f)
        entries_with_order = {}
        for item in config:
            if "Order" in item:
                order = item["Order"]
                entries_with_order[order] = LevelConfig(**item)
        # 1-> Level X , 2-> Level Y, ...
        # Sort the entries by 'Order'
        sorted_entries = dict(sorted(entries_with_order.items()))
        ret = OrderedDict()
        for _, level_config in sorted_entries.items():
            ret[level_config.Separator] = level_config
        return AspectsConfig(ret)

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

    def __repr__(self) -> str:
        return f"AspectsConfig(levels={self.levels})"


default_configs: AspectsConfig = AspectsConfig.init_from_file("config.json")

if __name__ == "__main__":
    config_dict = default_configs.levels
    print(config_dict)
    print(config_dict["="].Aspect)  # Should print "Functional"
    print(config_dict.keys())  # Should print the keys of the OrderedDict
