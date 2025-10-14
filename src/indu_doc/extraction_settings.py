import json
from dataclasses import dataclass, field, asdict
from indu_doc.common_page_utils import PageType
import logging

logger = logging.getLogger(__name__)

type rect = tuple[float, float, float, float]
@dataclass
class TableSetup:
    key_columns: dict[str, str]     # name -> role
    #
    description: str                = ""
    roi: rect                       = (0, 0, 0, 0)
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    # not sure about structure of those
    columns: dict[str, bool]        = field(default_factory=dict) # name -> include bool
    # TODO this is all extendable - make as dict
    overlap_test_roi: rect | None   = None
    expected_num_tables: int        = 1
    on_many_join: bool              = False # 
    on_many_no_header: bool         = False
    row_offset: int                 = 0 # -1 will demote header (make current heaser a 0th row), >0 will promote (make nth row a header)
    

@dataclass 
class PageSetup:
    tables: dict[str, TableSetup] # role -> TableSetup, e.g. cable_info_left -> {...} ; main -> {...}
    description: str            = ""
    search_name: str            = ""
    language: str               = ""


class ExtractionSettings:

    filename: str
    pages_setup: dict[PageType, PageSetup]

    def __getitem__(self, key) -> PageSetup:
        return self.pages_setup[key]
    
    def __setitem__(self, key, value):
        self.pages_setup[key] = value

    def __contains__(self, key) -> bool:
        return key in self.pages_setup

    def __init__(self, filename: str, pages_setup: dict[PageType, PageSetup] | None = None):
        self.filename = filename
        if pages_setup:
            self.pages_setup = pages_setup
            self.save()
        else:
            self.load()

    def to_enum(self) -> dict[PageType, str]:
        return {k: v.search_name for k, v in self.pages_setup.items()}

    def to_json(self) -> str:
        """Serialize a list of PageSetup objects to a JSON string."""
        return json.dumps({k.name: asdict(s) for k, s in self.pages_setup.items()}, indent=2)

    def from_json(self, json_str: str):
        """Deserialize JSON string back into a list of PageSetup objects."""
        settings: dict[PageType, PageSetup] = {}
        try:
            data = json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to load extraction settings: {e}")
            self.pages_setup = settings
            return
            
        for key, value in data.items():
            tables = {k: TableSetup(**v) for k, v in value["tables"].items()}
            settings[PageType[key]] = PageSetup(
                tables=tables,
                description=value.get("description", ""),
                search_name=value.get("search_name", ""),
                language=value.get("language", "")
            )
        self.pages_setup = settings

    def save(self):
        """Save list of PageSetup objects to a JSON file."""
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def load(self):
        """Load list of PageSetup objects from a JSON file."""
        with open(self.filename, "a+", encoding="utf-8") as f:
            f.seek(0)
            self.from_json(f.read())