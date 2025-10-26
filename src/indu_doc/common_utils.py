

from typing import Optional


def normalize_string(s: str) -> str:
    """Normalize a string for consistent searching."""
    return ' '.join(s.lower().strip().split())

def is_pin_tag(tag: str) -> bool:
    # every pin for error handling starts from ':'
    return tag.find(':') != -1


def split_pin_tag(tag_pin: str) -> tuple[str, Optional[str]]:
    # now I assume that pin starts from ':'
    tags = tag_pin.split(':', 1)
    # every pin for error handling starts from ':'
    return tags[0], None if len(tags) == 1 else ':' + tags[1]