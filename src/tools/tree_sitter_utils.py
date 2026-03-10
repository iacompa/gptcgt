"""
Tree-sitter utilities for code parsing.
Language detection from file extensions. Symbol extraction (classes,
functions, methods, imports) per language. Falls back to regex if
tree-sitter is not installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import get_logger

logger = get_logger("tools.tree_sitter")

_parser = None
_languages = {}


def _ensure_parser():
    """Lazy-load tree-sitter."""
    global _parser, _languages
    if _parser is not None:
        return
    try:
        from tree_sitter_languages import get_language

        _parser = True
        for lang in (
            "python",
            "javascript",
            "typescript",
            "tsx",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "ruby",
        ):
            try:
                _languages[lang] = get_language(lang)
            except Exception:
                pass
        logger.info(f"tree-sitter loaded with {len(_languages)} languages")
    except ImportError:
        _parser = False
        logger.warning("tree-sitter not available — using regex fallback")


EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".rb": "ruby",
}


def detect_language(file_path: Path) -> str | None:
    """Detect programming language from file extension."""
    return EXTENSION_LANGUAGE_MAP.get(file_path.suffix.lower())


@dataclass
class FileSymbols:
    """Extracted symbols from a single file."""

    path: Path
    language: str
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    methods: dict[str, list[str]] = field(default_factory=dict)  # class → [methods]
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    line_count: int = 0


def extract_symbols(file_path: Path, content: str) -> FileSymbols:
    """Extract top-level symbols. Uses tree-sitter if available, else regex."""
    language = detect_language(file_path)
    line_count = content.count("\n") + 1
    if language is None:
        return FileSymbols(path=file_path, language="unknown", line_count=line_count)

    _ensure_parser()
    if _parser is True and language in _languages:
        return _extract_with_tree_sitter(file_path, content, language, line_count)
    return _extract_with_regex(file_path, content, language, line_count)


def _extract_with_tree_sitter(file_path: Path, content: str, language: str, line_count: int) -> FileSymbols:
    """Extract symbols using tree-sitter AST parsing."""
    from tree_sitter_languages import get_parser

    parser = get_parser(language)
    tree = parser.parse(content.encode("utf-8"))
    root = tree.root_node
    symbols = FileSymbols(path=file_path, language=language, line_count=line_count)

    if language == "python":
        _extract_python(root, content, symbols)
    elif language in ("javascript", "typescript", "tsx"):
        _extract_js_ts(root, content, symbols)
    elif language == "rust":
        _extract_rust(root, content, symbols)
    elif language == "go":
        _extract_go(root, content, symbols)
    elif language == "java":
        _extract_java(root, content, symbols)
    return symbols


def _node_text(node, content: str) -> str:
    return content[node.start_byte : node.end_byte]


def _extract_python(root, content: str, symbols: FileSymbols) -> None:
    for node in root.children:
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                cls = _node_text(name_node, content)
                symbols.classes.append(cls)
                body = node.child_by_field_name("body")
                if body:
                    methods = []
                    for child in body.children:
                        if child.type == "function_definition":
                            mn = child.child_by_field_name("name")
                            if mn:
                                name = _node_text(mn, content)
                                if not name.startswith("_") or name == "__init__":
                                    methods.append(name)
                    symbols.methods[cls] = methods
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                fn = _node_text(name_node, content)
                if not fn.startswith("_"):
                    symbols.functions.append(fn)
        elif node.type in ("import_statement", "import_from_statement"):
            symbols.imports.append(_node_text(node, content).strip())


def _extract_js_ts(root, content: str, symbols: FileSymbols) -> None:
    for node in root.children:
        if node.type == "class_declaration":
            n = node.child_by_field_name("name")
            if n:
                symbols.classes.append(_node_text(n, content))
        elif node.type in ("function_declaration", "lexical_declaration"):
            n = node.child_by_field_name("name")
            if n:
                symbols.functions.append(_node_text(n, content))
        elif node.type == "import_statement":
            symbols.imports.append(_node_text(node, content).strip())
        elif node.type == "export_statement":
            symbols.exports.append(_node_text(node, content).strip()[:100])


def _extract_rust(root, content: str, symbols: FileSymbols) -> None:
    for node in root.children:
        if node.type in ("struct_item", "enum_item"):
            n = node.child_by_field_name("name")
            if n:
                symbols.classes.append(_node_text(n, content))
        elif node.type == "function_item":
            n = node.child_by_field_name("name")
            if n:
                symbols.functions.append(_node_text(n, content))
        elif node.type == "use_declaration":
            symbols.imports.append(_node_text(node, content).strip())


def _extract_go(root, content: str, symbols: FileSymbols) -> None:
    for node in root.children:
        if node.type == "type_declaration":
            for spec in node.children:
                if spec.type == "type_spec":
                    n = spec.child_by_field_name("name")
                    if n:
                        symbols.classes.append(_node_text(n, content))
        elif node.type == "function_declaration":
            n = node.child_by_field_name("name")
            if n:
                name = _node_text(n, content)
                if name[0].isupper():
                    symbols.functions.append(name)
        elif node.type == "import_declaration":
            symbols.imports.append(_node_text(node, content).strip())


def _extract_java(root, content: str, symbols: FileSymbols) -> None:
    for node in root.children:
        if node.type == "class_declaration":
            n = node.child_by_field_name("name")
            if n:
                symbols.classes.append(_node_text(n, content))
        elif node.type == "import_declaration":
            symbols.imports.append(_node_text(node, content).strip())


def _extract_with_regex(file_path: Path, content: str, language: str, line_count: int) -> FileSymbols:
    """Fallback regex extraction when tree-sitter unavailable."""
    symbols = FileSymbols(path=file_path, language=language, line_count=line_count)
    if language == "python":
        symbols.classes = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
        symbols.functions = [f for f in re.findall(r"^def\s+(\w+)", content, re.MULTILINE) if not f.startswith("_")]
        symbols.imports = re.findall(r"^(?:from\s+\S+\s+)?import\s+.+", content, re.MULTILINE)
    elif language in ("javascript", "typescript", "tsx"):
        symbols.classes = re.findall(r"class\s+(\w+)", content)
        symbols.functions = re.findall(r"(?:function|const|let)\s+(\w+)\s*(?:=\s*(?:\(|async)|[\(<])", content)
        symbols.imports = re.findall(r"^import\s+.+", content, re.MULTILINE)
    elif language == "rust":
        symbols.classes = re.findall(r"(?:struct|enum)\s+(\w+)", content)
        symbols.functions = re.findall(r"(?:pub\s+)?fn\s+(\w+)", content)
    elif language == "go":
        symbols.classes = re.findall(r"type\s+(\w+)\s+struct", content)
        symbols.functions = re.findall(r"func\s+(\w+)\s*\(", content)
    return symbols
