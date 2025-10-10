from lark import Lark, Transformer, v_args

class Filter:
    def __init__(self, dotted_path : list[str], dotted_param: str | None, value: str | None):
        self.dotted_path = dotted_path
        self.dotted_param = dotted_param
        self.value = value

    def __repr__(self):
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
    def start(self, *children):
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
        return tag_word

    def filter(self, dotted_name_result, value=None):
        dotted_path, dotted_param = dotted_name_result
        # If a value exists, strip leading/trailing whitespace.
        # This handles cases like "@guid=\n" correctly, resulting in an empty string.
        final_value = value.strip() if value is not None else None
        return Filter(dotted_path=dotted_path, dotted_param=dotted_param, value=final_value)

    def dotted_name(self, *children):
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
        # Handles the `value` rule, including an empty `()` which results in val=None.
        return val if val is not None else ""

    def param_text(self, s):
        return s.value

    # Transform leaf tokens into strings
    def NOSPACESWORD(self, w):
        return w.value
    
    def NUMBER(self, n):
        return n.value

    def VALUE_TEXT(self, v):
        return v.value

parser = Lark(search_grammar)

def run_parser(program) -> tuple[str | None, list[Filter]]:
    """
    Parses the program text, transforms it into Query objects, and returns the tag and query list.
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