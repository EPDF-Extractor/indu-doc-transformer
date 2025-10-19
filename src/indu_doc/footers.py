from dataclasses import dataclass

import logging

logger = logging.getLogger(__name__)


@dataclass
class PageFooter:
    project_name: str
    product_name: str
    tags: list[str]  # list of the tag strings found in the footer

    def __hash__(self) -> int:
        return hash((self.project_name, self.product_name, tuple(self.tags)))

    def __eq__(self, other) -> bool:
        if not isinstance(other, PageFooter):
            return False
        return (
            self.project_name == other.project_name
            and self.product_name == other.product_name
            and self.tags == other.tags
        )


