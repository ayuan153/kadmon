"""Tree-sitter based parser for extracting symbols from source files."""

from pathlib import Path

import tree_sitter as ts


EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
}

# Lazy-loaded grammar modules
_GRAMMAR_MODULES = {
    "python": "tree_sitter_python",
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
}


def _load_language(language: str) -> ts.Language | None:
    """Load a tree-sitter Language from the grammar package."""
    mod_name = _GRAMMAR_MODULES.get(language)
    if not mod_name:
        return None
    try:
        import importlib
        mod = importlib.import_module(mod_name)
        # typescript module exposes language_typescript() and language_tsx()
        if language == "typescript":
            return ts.Language(mod.language_typescript())
        return ts.Language(mod.language())
    except (ImportError, AttributeError):
        return None


class SymbolParser:
    def __init__(self):
        self._parsers: dict[str, ts.Parser] = {}

    def _get_parser(self, language: str) -> ts.Parser | None:
        if language not in self._parsers:
            lang = _load_language(language)
            if not lang:
                return None
            self._parsers[language] = ts.Parser(lang)
        return self._parsers[language]

    def parse_file(self, file_path: str) -> list[dict]:
        ext = Path(file_path).suffix
        language = EXTENSION_MAP.get(ext)
        if not language:
            return []

        try:
            source = Path(file_path).read_bytes()
        except (OSError, IOError):
            return []

        parser = self._get_parser(language)
        if not parser:
            return []
        tree = parser.parse(source)
        lines = source.split(b"\n")

        symbols = []
        if language == "python":
            self._walk_python(tree.root_node, lines, symbols, parent_class=None)
        else:
            self._walk_js_ts(tree.root_node, lines, symbols, parent_class=None)
        return symbols

    def _make_symbol(self, name, sym_type, kind, node, lines, parent_name=None, signature=None):
        if signature is None:
            signature = lines[node.start_point[0]].decode("utf-8", errors="replace").rstrip()
        return {
            "name": name,
            "type": sym_type,
            "kind": kind,
            "start_line": node.start_point[0] + 1,
            "start_col": node.start_point[1] + 1,
            "end_line": node.end_point[0] + 1,
            "end_col": node.end_point[1] + 1,
            "parent_name": parent_name,
            "signature": signature,
        }

    # --- Python ---

    def _walk_python(self, node, lines, symbols, parent_class):
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                symbols.append(self._make_symbol(name, "definition", "class", node, lines))
                for child in node.children:
                    self._walk_python(child, lines, symbols, parent_class=name)
            return

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                kind = "method" if parent_class else "function"
                symbols.append(self._make_symbol(
                    name, "definition", kind, node, lines, parent_name=parent_class
                ))
            for child in node.children:
                self._walk_python(child, lines, symbols, parent_class=parent_class)
            return

        if node.type == "decorated_definition":
            # Process the inner definition with context preserved
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    self._walk_python(child, lines, symbols, parent_class=parent_class)
            return

        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                name = self._extract_call_name(func_node)
                if name:
                    symbols.append(self._make_symbol(name, "reference", "call", node, lines))

        for child in node.children:
            self._walk_python(child, lines, symbols, parent_class=parent_class)

    # --- JavaScript/TypeScript ---

    def _walk_js_ts(self, node, lines, symbols, parent_class):
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                symbols.append(self._make_symbol(name, "definition", "class", node, lines))
                for child in node.children:
                    self._walk_js_ts(child, lines, symbols, parent_class=name)
            return

        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                symbols.append(self._make_symbol(name, "definition", "function", node, lines))
            for child in node.children:
                self._walk_js_ts(child, lines, symbols, parent_class=parent_class)
            return

        if node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode()
                symbols.append(self._make_symbol(
                    name, "definition", "method", node, lines, parent_name=parent_class
                ))
            for child in node.children:
                self._walk_js_ts(child, lines, symbols, parent_class=parent_class)
            return

        if node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node and value_node and value_node.type == "arrow_function":
                name = name_node.text.decode()
                symbols.append(self._make_symbol(name, "definition", "function", node, lines))
                for child in node.children:
                    self._walk_js_ts(child, lines, symbols, parent_class=parent_class)
                return

        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node:
                name = self._extract_call_name(func_node)
                if name:
                    symbols.append(self._make_symbol(name, "reference", "call", node, lines))

        for child in node.children:
            self._walk_js_ts(child, lines, symbols, parent_class=parent_class)

    # --- Helpers ---

    def _extract_call_name(self, node) -> str | None:
        """Extract the function/method name from a call's function node."""
        if node.type == "identifier":
            return node.text.decode()
        if node.type == "attribute" or node.type == "member_expression":
            # e.g., obj.method — extract 'method'
            prop = node.child_by_field_name("attribute") or node.child_by_field_name("property")
            if prop:
                return prop.text.decode()
        return None
