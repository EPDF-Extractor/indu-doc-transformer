"""
Search query parser using Lark.

This module provides parsing functionality for search queries used in the InduDoc system.
It uses the Lark parsing library to parse complex query strings with filters, tags,
and attribute matching.
"""

from lark import Lark, Transformer, v_args


class Filter:
    """Represents a parsed filter from a search query.
    
    :param dotted_path: List of path components for the filter target
    :type dotted_path: list[str]
    :param dotted_param: Optional parameter specification
    :type dotted_param: str | None
    :param value: Optional value to match against
    :type value: str | None
    """
    
    def __init__(self, dotted_path : list[str], dotted_param: str | None, value: str | None):
        """Initialize a Filter instance.
        
        :param dotted_path: List of path components
        :type dotted_path: list[str]
        :param dotted_param: Optional parameter specification
        :type dotted_param: str | None
        :param value: Optional value to match
        :type value: str | None
        """
        self.dotted_path = dotted_path
        self.dotted_param = dotted_param
        self.value = value

    def __repr__(self):
        """Return string representation of the filter.
        
        :return: String representation
        :rtype: str
        """
        return f"Query(dotted_path={self.dotted_path}, dotted_param={self.dotted_param}, value={self.value})"

search_grammar = """
    start: tag_assign? filter*

    tag_assign: TAGWORD
    TAGWORD: /([=+-.][A-Za-z0-9_]+)+/
    filter: "@" dotted_name ("=" value)?

    dotted_name: NOSPACESWORD ("." NOSPACESWORD)* ("(" param_text? ")")?

    value: VALUE_TEXT | "(" VALUE_TEXT? ")"
    
    param_text: /[^)]+/
    
    // Match any characters except '@' to capture values, including whitespace.
    VALUE_TEXT: /[^@]+/

    // Words don't contain special characters like =, ., (, ), @ or whitespace.
    NOSPACESWORD: /[^=.\\s()@]+/
    NUMBER: /\\d+/

    %import common.WS
    %ignore WS
"""

# A Transformer to walk the parse tree and create Query objects.
@v_args(inline=True) # Makes visitor methods receive children directly
class QueryTransformer(Transformer):
    """Transformer for converting Lark parse trees into Filter objects.
    
    This class transforms the parsed grammar into structured Filter objects
    that can be used for searching and filtering document data.
    """
    
    def start(self, *children):
        """Transform the root of the parse tree.
        
        :param children: Child nodes from the parse tree
        :return: Tuple of (tag, queries)
        :rtype: tuple[str | None, list[Filter]]
        """
        tag = None
        queries = []
        if children:
            if isinstance(children[0], str):
                tag = children[0]
                queries = children[1:]
            else:
                queries = children
        return tag, list(queries)

    def tag_assign(self, tag_word):
        """Transform a tag assignment.
        
        :param tag_word: The tag word token
        :return: The tag word
        :rtype: str
        """
        return tag_word

    def filter(self, dotted_name_result, value=None):
        """Transform a filter expression.
        
        :param dotted_name_result: Result from dotted_name transformation
        :param value: Optional value to match
        :return: Filter object
        :rtype: Filter
        """
        dotted_path, dotted_param = dotted_name_result
        # If a value exists, strip leading/trailing whitespace.
        # This handles cases like "@guid=\n" correctly, resulting in an empty string.
        final_value = value.strip() if value is not None else None
        return Filter(dotted_path=dotted_path, dotted_param=dotted_param, value=final_value)

    def dotted_name(self, *children):
        """Transform a dotted name expression.
        
        :param children: Child tokens
        :return: Tuple of (path, param)
        :rtype: tuple[list, str | None]
        """
        path = []
        param = None
        # The parameter text will be the last child if it exists and will be a string.
        if len(children) == 1 and isinstance(children[0], str):
            # Only a single word, no dots or params.
            path_tokens = [children[0]]
        elif children and isinstance(children[-1], str):
            param = children[-1]
            path_tokens = children[:-1]
        else:
            path_tokens = children
        
        path = list(path_tokens)
        return path, param
    
    def value(self, val=None):
        """Transform a value expression.
        
        :param val: The value token
        :return: The processed value
        :rtype: str
        """
        # Handles the `value` rule, including an empty `()` which results in val=None.
        return val if val is not None else ""

    def param_text(self, s):
        """Transform parameter text.
        
        :param s: Parameter text token
        :return: The parameter text
        :rtype: str
        """
        return s.value

    # Transform leaf tokens into strings
    def NOSPACESWORD(self, w):
        """Transform a word token.
        
        :param w: Word token
        :return: The word value
        :rtype: str
        """
        return w.value
    
    def NUMBER(self, n):
        """Transform a number token.
        
        :param n: Number token
        :return: The number value
        :rtype: str
        """
        return n.value

    def VALUE_TEXT(self, v):
        """Transform value text.
        
        :param v: Value text token
        :return: The value text
        :rtype: str
        """
        return v.value

parser = Lark(search_grammar)

def run_parser(program) -> tuple[str | None, list[Filter]]:
    """Parse a search program string into tag and filter objects.
    
    :param program: The search query string to parse
    :type program: str
    :return: Tuple containing optional tag and list of Filter objects
    :rtype: tuple[str | None, list[Filter]]
    """
    parse_tree = parser.parse(program)
    tag, queries = QueryTransformer().transform(parse_tree)
    return tag, queries

if __name__ == "__main__":
    def test():
        text = """
        @src.tag==E+A1-x @links.part-number=LLAP
        @page=4
        @guid=
        @tag
        @src=As
        @dest=ee
        @links.srcpin=43
        @links.destpin=44
        @links.attributes(wire strong 2)= rew ks
        @attribute(Length)=12m
        """
        text = "@links.attributes(color)=b"
        tag, queries = run_parser(text)
        print(f"Tag: {tag}")
        print("\nQueries:")
        for query in queries:
            print(f"  {query}")
    test()