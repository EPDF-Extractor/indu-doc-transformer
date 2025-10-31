"""
Tag and aspect parsing for industrial documentation.

This module provides classes and functions for parsing and managing hierarchical
tags with aspects (separators and values) commonly found in industrial electrical
diagrams. Tags represent equipment identifiers with multiple hierarchical levels
separated by specific characters.
"""

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
    """
    Represents a single aspect (separator + value) of a tag.
    
    An aspect is a component of a hierarchical tag, consisting of a separator
    character and a value. For example, in "+A1-M2", "+A1" and "-M2" are aspects.
    
    :param separator: The separator character (e.g., "+", "-", "=")
    :type separator: str
    :param value: The value following the separator (e.g., "A1", "M2")
    :type value: str
    :param attributes: Optional list of attributes to attach
    :type attributes: list[Attribute] | None, optional
    """
    
    def __init__(
        self,
        separator: str,
        value: str,
        attributes: list[Attribute] | None = None,
    ) -> None:
        """
        Initialize an Aspect.
        
        :param separator: The separator character
        :type separator: str
        :param value: The value following the separator
        :type value: str
        :param attributes: Optional list of attributes, defaults to None
        :type attributes: list[Attribute] | None, optional
        """
        super().__init__(attributes)
        self.separator: str = separator
        self.value: str = value

    def get_guid(self) -> str:
        """
        Get the globally unique identifier for this aspect.
        
        Uses the same logic as for xtargets. Every time we process the PDF,
        we generate the same ID for the same aspect. The aspect string should
        always be the same for the same object as it appears in the PDF.
        
        :return: A globally unique identifier string
        :rtype: str
        """
        # same logic as for xtargets
        # Everytime we process the pdf -> generate the same ID for the same tag
        # The tag string should always be the same for the same object -> It's how we see them in the PDF
        return str(uuid.UUID(bytes=hashlib.md5(str(self).encode("utf-8")).digest()))
    
    def add_attribute(self, attribute: Attribute) -> None:
        """
        Add an attribute to this aspect.
        
        :param attribute: The attribute to add
        :type attribute: Attribute
        """
        self.attributes.add(attribute)

    def __str__(self) -> str:
        """
        Return string representation of the aspect.
        
        :return: String in format "separator + value"
        :rtype: str
        """
        return f"{self.separator}{self.value}"

    def __repr__(self) -> str:
        """
        Return detailed string representation of the aspect.
        
        :return: String showing aspect and its attributes
        :rtype: str
        """
        return f"Aspect({str(self)}, attributes={self.attributes})"
    
    def __eq__(self, other: object) -> bool:
        """
        Check equality with another Aspect.
        
        :param other: Another object to compare with
        :return: True if separator, value, and attributes are equal
        :rtype: bool
        """
        if not isinstance(other, Aspect):
            return False
        return self.separator == other.separator and self.value == other.value and self.attributes == other.attributes
    
    def __hash__(self) -> int:
        """
        Return hash value for this aspect.
        
        :return: Hash value based on GUID
        :rtype: int
        """
        return hash(self.get_guid())


class Tag:
    """
    Represents a hierarchical tag with its associated aspects.
    
    A tag represents an equipment or component identifier in industrial diagrams.
    It consists of multiple aspects (separator-value pairs) that form a hierarchy.
    For example: "+A1-M2=K1" has aspects ["+A1", "-M2", "=K1"].
    
    :param tag_: The raw tag string
    :type tag_: str
    :param config: Configuration for aspect parsing
    :type config: AspectsConfig
    
    :ivar tag_str: The processed tag string (may exclude terminal separators)
    :ivar aspects: Dictionary mapping separator to tuple of aspects, None until parsed
    """

    def __init__(self, tag_: str, config: AspectsConfig):
        """
        Initialize a Tag.
        
        :param tag_: The raw tag string to parse
        :type tag_: str
        :param config: Configuration defining aspect levels and separators
        :type config: AspectsConfig
        """
        self.config = config
        self.tag_str = self.get_tag_str(tag_)
        self.aspects: dict[str, tuple[Aspect, ...]] | None = None

    def get_tag_str(self, tag_: str) -> str:
        """
        Extract the base tag string, excluding terminal separator and pin designation.
        
        Removes the pin designation (anything after ':') from the tag string.
        
        :param tag_: The raw tag string that may include pin designation
        :type tag_: str
        :return: The base tag string without pin designation
        :rtype: str
        """
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
        Create a complete tag by merging with footer information.
        
        Merges incomplete tag strings with footer tags to create complete
        hierarchical tags. Takes the order of levels into consideration.
        This is needed for merging footer tags with incomplete page tags.
        
        :param tag_str: The incomplete tag string from the page
        :type tag_str: str
        :param footer: The page footer containing additional tag information
        :type footer: PageFooter
        :param config: Configuration for aspect parsing
        :type config: AspectsConfig
        :return: A new Tag object with merged information
        :rtype: Tag
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
        """
        Set the aspects dictionary for this tag.
        
        :param aspects: Dictionary mapping separators to tuples of Aspect objects
        :type aspects: dict[str, tuple[Aspect, ...]]
        """
        self.aspects = aspects


    def get_tag_parts(self) -> dict[str, tuple[str, ...]]:
        """
        Get the tag parts as a dictionary of separators to value tuples.
        
        Returns tag parts based on the configuration. If aspects are already
        set, extracts values from them. Otherwise, parses the tag string.
        
        :return: Dictionary mapping separators to tuples of their values, ordered by appearance
        :rtype: dict[str, tuple[str, ...]]
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
        Get the aspects of this tag.
        
        Returns the aspects as a dictionary mapping separators to their
        corresponding Aspect objects. Only returns aspects that are configured.
        
        :return: Dictionary of configured aspects, or None if no aspects are set
        :rtype: dict[str, tuple[Aspect, ...]] | None
        """
        if not self.aspects:
            return None
        configured_aspects = {sep.Separator: self.aspects[sep.Separator] for sep in self.config.to_list() if sep.Separator in self.aspects}
        return configured_aspects

    @staticmethod
    def is_valid_tag(tag_str: str, config: AspectsConfig) -> bool:
        """
        Validate if a tag string can be parsed based on the configuration.
        
        Checks if the provided tag string can be parsed into a Tag object
        based on the provided configurations.
        
        :param tag_str: The tag string to validate
        :type tag_str: str
        :param config: The configurations to use for validation
        :type config: AspectsConfig
        :return: True if the tag string is valid, otherwise False
        :rtype: bool
        :raises NotImplementedError: This method is not yet implemented/tested
        """
        raise NotImplementedError("This method is not tested yet.")
        seps = list(config.separators())
        pattern_accepted_text = re.compile(
            rf"[{re.escape(''.join(seps))}][A-Z0-9][A-Z0-9&/:;.]*"
        )
        return pattern_accepted_text.match(tag_str) is not None

    def __repr__(self):
        """
        Return string representation of the tag.
        
        :return: String showing the tag string
        :rtype: str
        """
        return f"Tag(tag_str='{self.tag_str}'"

    def __eq__(self, other):
        """
        Check equality with another Tag.
        
        :param other: Another object to compare with
        :return: True if tag strings are equal
        :rtype: bool
        """
        if not isinstance(other, Tag):
            return False
        return self.tag_str == other.tag_str

    def __lt__(self, other):
        """
        Compare if this tag is less than another tag.
        
        :param other: Another Tag to compare with
        :return: True if this tag's string is less than the other's
        :raises TypeError: If other is not a Tag instance
        """
        if not isinstance(other, Tag):
            return NotImplemented
        return self.tag_str < other.tag_str

    def __hash__(self):
        """
        Return hash value for this tag.
        
        :return: Hash value based on tag string
        :rtype: int
        """
        return hash(self.tag_str)


def try_parse_tag(tag_str: str, configs: AspectsConfig) -> dict[str, tuple[str, ...]] | None:
    """
    Attempt to parse a tag string into its component parts.
    
    Parses a tag string based on the provided separator configuration,
    extracting the values associated with each separator. Returns a dictionary
    mapping separators to tuples of their values.
    
    :param tag_str: The tag string to parse
    :type tag_str: str
    :param configs: The configurations defining valid separators
    :type configs: AspectsConfig
    :return: Dictionary mapping separators to tuples of values, or None if parsing fails
    :rtype: dict[str, tuple[str, ...]] | None
    
    Example:
        >>> config = AspectsConfig.init_from_list([
        ...     {"Separator": "+", "Aspect": "Location"},
        ...     {"Separator": "-", "Aspect": "Device"}
        ... ])
        >>> try_parse_tag("+A1-M2", config)
        {'+': ('A1',), '-': ('M2',)}
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
