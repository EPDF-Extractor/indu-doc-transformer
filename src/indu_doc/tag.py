from __future__ import annotations
from typing import OrderedDict
from indu_doc.configs import AspectsConfig, LevelConfig
import re
import logging
import uuid
import hashlib

from .attributed_base import AttributedBase
from .attributes import Attribute

from indu_doc.footers import PageFooter

logger = logging.getLogger(__name__)


class Aspect(AttributedBase):
    def __init__(
        self,
        separator: str,
        value: str,
        attributes: list[Attribute] | None = None,
    ) -> None:
        super().__init__(attributes)
        self.separator: str = separator
        self.value: str = value

    def get_guid(self) -> str:
        # same logic as for xtargets
        # Everytime we process the pdf -> generate the same ID for the same tag
        # The tag string should always be the same for the same object -> It's how we see them in the PDF
        return str(uuid.UUID(bytes=hashlib.md5(str(self).encode("utf-8")).digest()))
    
    def add_attribute(self, attribute: Attribute) -> None:
        self.attributes.add(attribute)

    def __str__(self) -> str:
        return f"{self.separator}{self.value}"

    def __repr__(self) -> str:
        return f"Aspect({str(self)}, attributes={self.attributes})"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Aspect):
            return False
        return self.separator == other.separator and self.value == other.value and self.attributes == other.attributes
    
    def __hash__(self) -> int:
        return hash(self.get_guid())


class Tag:
    """
    Represents a tag with its associated parts.

    Attributes:
        tag_str (str): The original tag string.
    """

    def __init__(self, tag_: str, config: AspectsConfig):
        self.config = config
        self.tag_str = self.get_tag_str(tag_)
        self.aspects: dict[str, tuple[Aspect, ...]] | None = None

    def get_tag_str(self, tag_: str) -> str:
        # TODO: We want to consider the terminal separator from the config, change config to mark the terminal separator
        # terminal_sep = self.config["Pins"] if "Pins" in self.config.levels else None
        # if not terminal_sep:
        #     return tag_

        # otherwise we return everything before the terminal separator
        terminal_index = tag_.find(":")
        if terminal_index != -1:
            return tag_[:terminal_index]
        return tag_

    @classmethod
    def get_tag_with_footer(
        cls, tag_str: str, footer: PageFooter, config: AspectsConfig
    ) -> Tag:
        """
        Merge this tag with another tag, We take the order of levels into considerations
        This Function is needed to Merging Footer Tags with the page incomplete tags.
        -> It returns a new Tag object.
        """
        temp_tag = cls(tag_str, config)
        temp_tag_parts = temp_tag.get_tag_parts()
        footer_tag_parts = {}
        for foo in footer.tags:
            parsed = try_parse_tag(foo, config)
            if not parsed:
                continue

            for sep, val in parsed.items():
                # TODO: Ignore the & separator for now, we might want to handle it differently in the future
                # we also ignore empty aspects
                if sep != "&" and val and val != ("",):
                    # footers only have one value per separator, Hopefully!
                    footer_tag_parts[sep] = val[0]

        prepended_part = ""
        for sep in config.separators:
            if sep in temp_tag_parts and temp_tag_parts[sep]:
                break
            if sep in footer_tag_parts:
                prepended_part += f"{sep}{footer_tag_parts[sep]}"

        if prepended_part:
            logger.info(
                f"Prepended {prepended_part} to {tag_str} from footer {footer.tags}"
            )
        return cls(prepended_part + tag_str, config)
    

    def set_aspects(self, aspects: dict[str, tuple[Aspect, ...]]):
        self.aspects = aspects


    def get_tag_parts(self) -> dict[str, tuple[str, ...]]:
        """
        Returns the tag parts but based on a different, provided configuration.
        Returns:
            dict[str, tuple[str, ...]]: A dictionary mapping separators to their corresponding values, ordered by their appearance in the tag string.
        """
        aspects = self.get_aspects()
        if aspects:
            return {sep: tuple([v.value for v in vals]) for sep, vals in aspects.items()}
        else:
            # only do parsing if aspects are not set
            new_tag_parts = try_parse_tag(self.tag_str, self.config)
            if new_tag_parts is not None:
                return {sep: (new_tag_parts[sep] if sep in new_tag_parts else ()) for sep in self.config.separator_ge(new_tag_parts.keys())}
            else:
                logger.warning(f"Failed to parse tag string: {self.tag_str} ")
                return {}
        
    def get_aspects(self) -> dict[str, tuple[Aspect, ...]] | None:
        """
        Returns the aspects of the tag as a dictionary mapping separators to their corresponding Aspect objects.
        If no aspects are set, returns None.
        """
        if not self.aspects:
            return None
        configured_aspects = {sep.Separator: self.aspects[sep.Separator] for sep in self.config.to_list() if sep.Separator in self.aspects}
        return configured_aspects

    @staticmethod
    def is_valid_tag(tag_str: str, config: AspectsConfig) -> bool:
        """
        Validates if the provided tag string can be parsed into a Tag object based on the provided configurations.
        Args:
            tag_str (str): The tag string to validate.
            config (AspectsConfig): The configurations to use for validation.
        Returns:
            bool: True if the tag string is valid, otherwise False.
        """
        raise NotImplementedError("This method is not tested yet.")
        seps = list(config.separators())
        pattern_accepted_text = re.compile(
            rf"[{re.escape(''.join(seps))}][A-Z0-9][A-Z0-9&/:;.]*"
        )
        return pattern_accepted_text.match(tag_str) is not None

    def __repr__(self):
        return f"Tag(tag_str='{self.tag_str}'"

    def __eq__(self, other):
        if not isinstance(other, Tag):
            return False
        return self.tag_str == other.tag_str

    def __lt__(self, other):
        if not isinstance(other, Tag):
            return NotImplemented
        return self.tag_str < other.tag_str

    def __hash__(self):
        return hash(self.tag_str)


def try_parse_tag(tag_str: str, configs: AspectsConfig) -> dict[str, tuple[str, ...]] | None:
    """
    Attempts to parse a tag string into a Tag object based on the provided configurations.
    Args:
        tag_str (str): The tag string to parse.
        configs (AspectsConfig): The configurations to use for parsing.
    Returns:
    """
    tag_str = tag_str.strip()

    if not tag_str:
        logger.debug(f"Empty tag string provided.")
        return {}

    # We might have the case where we have separators like = and == which can cause overlapping, regex always matches the longest first, which is what we want.
    separators_index = []
    pattern = "|".join(re.escape(separator)
                       for separator in configs.separators)
    matches = list(re.finditer(pattern, tag_str))

    if not matches or matches[0].start() != 0:
        logger.debug(f"Tag can not have anything appear before first separator.")
        return None

    for match in matches:
        separator = match.group(0)
        start_index = match.start()
        separators_index.append((start_index, separator))

    if not separators_index:
        logger.warning(f"No valid separators found in tag string: {tag_str}")
        return None

    tags_coll: dict[str, list[str]] = {}
    for i, (start_index, separator) in enumerate(separators_index):
        st_idx = start_index + len(separator)
        end_index = (
            separators_index[i + 1][0]
            if i + 1 < len(separators_index)
            else len(tag_str)
        )
        l: list[str] = tags_coll.get(separator, [])
        l.append(tag_str[st_idx:end_index].strip())
        tags_coll[separator] = l

    return {sep: tuple(vals) for sep, vals in tags_coll.items()}


if __name__ == "__main__":
    # Unit test for try_parse_tag
    logging.basicConfig(level=logging.DEBUG)

    configs: AspectsConfig = AspectsConfig(
        OrderedDict(
            {
                "===": LevelConfig(Separator="=", Aspect="Functional"),
                "==": LevelConfig(Separator="+", Aspect="Location"),
                "=": LevelConfig(Separator="-", Aspect="Product"),
                "+": LevelConfig(Separator="-", Aspect="Product"),
            }
        )
    )
    tag_str = "++A=M1=M2"
    tag = try_parse_tag(tag_str, configs)
    if tag:
        logger.debug("Parsed tags: %s", tag)
    else:
        logger.debug("Failed to parse tag string.")

    # some test cases for get_tag_with_footer
    footer = PageFooter(
        project_name="ProjectX",
        product_name="ProductY",
        tags=["=Prod", "==Loc", "===Func"],
    )
    tag1 = Tag.get_tag_with_footer("=Prod", footer, configs)
    assert tag1.tag_str == "===Func==Loc=Prod", (
        f"Expected '===Func==Loc=Prod', got '{tag1.tag_str}'"
    )
    assert tag1.get_tag_parts() == {"=": ("Prod",), "==": ("Loc",), "===": ("Func",)}, (
        f"Expected parts {{'=': ('Prod',), '==': ('Loc',), '===': ('Func',)}}, got {tag1.get_tag_parts()}"
    )
