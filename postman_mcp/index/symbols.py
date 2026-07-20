"""Per-file symbol extraction — language-level only, never framework-level.

Two backends behind one function:

- **Python** — stdlib ``ast``: exact line spans, decorators, bases, signatures.
- **Everything else** — a deliberately simple regex backend: classes,
  functions, arrow-consts, with ``@Annotation`` lines attached and line spans
  from brace matching. This is the documented "degraded index" mode; a
  tree-sitter backend (``tree-sitter-language-pack``) replaces it behind this
  same interface in a later phase without changing any caller.

Decorator/annotation text is stored raw. That is what lets the retrieval layer
find "the symbol whose decorator mentions ``/users``" without this module ever
knowing that ``@router.post`` is FastAPI and ``@Post`` is NestJS.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class SymbolField:
    """One class attribute — a Pydantic/dataclass-style field, own-class only.

    Populated only by the Python (``ast``) backend; the regex backend for other
    languages never fills this in (see ``Symbol.language``), so field-grounding
    checks downstream can tell "not captured" from "confirmed absent."
    """

    name: str
    annotation: str = ""    # raw `ast.unparse` text; "" for an untyped assignment
    has_default: bool = False
    line: int = 0

    def to_doc(self) -> dict:
        return {"name": self.name, "annotation": self.annotation,
                "has_default": self.has_default, "line": self.line}

    @classmethod
    def from_doc(cls, d: dict) -> "SymbolField":
        return cls(**d)


@dataclass
class Symbol:
    name: str
    kind: str               # "class" | "function" | "method"
    file: str               # repo-relative posix path
    line_start: int         # includes decorator lines
    line_end: int
    parent: str = ""        # enclosing class name for methods
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    signature: str = ""
    fields: list[SymbolField] = field(default_factory=list)  # class attributes; Python-only
    language: str = ""      # "python" | "typescript" | ... ; "" for legacy/unknown

    @property
    def qualname(self) -> str:
        return f"{self.parent}.{self.name}" if self.parent else self.name

    def to_doc(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "file": self.file,
            "line_start": self.line_start, "line_end": self.line_end,
            "parent": self.parent, "decorators": self.decorators,
            "bases": self.bases, "signature": self.signature,
            "fields": [f.to_doc() for f in self.fields], "language": self.language,
        }

    @classmethod
    def from_doc(cls, d: dict) -> "Symbol":
        d = dict(d)
        d["fields"] = [SymbolField.from_doc(f) for f in d.get("fields", [])]
        return cls(**d)


def extract_symbols(path: str, language: str, text: str) -> list[Symbol]:
    if not language:
        return []
    if language == "python":
        return _python_symbols(path, text)
    return _regex_symbols(path, text, language)


# -- Python backend (stdlib ast) ---------------------------------------------


def _python_symbols(path: str, text: str) -> list[Symbol]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out: list[Symbol] = []
    for node in tree.body:
        _collect_py(node, path, parent="", out=out)
    return out


def _collect_py(node: ast.AST, path: str, parent: str, out: list[Symbol]) -> None:
    if isinstance(node, ast.ClassDef):
        out.append(_py_symbol(node, path, "class", parent))
        for child in node.body:
            _collect_py(child, path, parent=node.name, out=out)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        kind = "method" if parent else "function"
        out.append(_py_symbol(node, path, kind, parent))


def _class_fields(node: ast.ClassDef) -> list["SymbolField"]:
    """Own class-body attributes only — no recursion into nested class bodies
    (e.g. Pydantic's ``class Config:`` idiom keeps its own separate ``Symbol``)."""
    out: list[SymbolField] = []
    for child in node.body:
        if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            try:
                annotation = ast.unparse(child.annotation)
            except Exception:  # pragma: no cover - unparse edge case
                annotation = ""
            out.append(SymbolField(
                name=child.target.id, annotation=annotation,
                has_default=child.value is not None, line=child.lineno,
            ))
        elif isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    out.append(SymbolField(name=target.id, has_default=True, line=child.lineno))
    return out


def _py_symbol(node, path: str, kind: str, parent: str) -> Symbol:
    decorators = []
    start = node.lineno
    for dec in node.decorator_list:
        try:
            decorators.append("@" + ast.unparse(dec))
        except Exception:  # pragma: no cover - unparse edge case
            decorators.append("@<unparseable>")
        start = min(start, dec.lineno)
    bases = []
    fields: list[SymbolField] = []
    if isinstance(node, ast.ClassDef):
        for b in node.bases:
            try:
                bases.append(ast.unparse(b))
            except Exception:  # pragma: no cover
                pass
        signature = f"class {node.name}"
        fields = _class_fields(node)
    else:
        try:
            args = ast.unparse(node.args)
        except Exception:  # pragma: no cover
            args = "..."
        signature = f"def {node.name}({args})"
    return Symbol(
        name=node.name, kind=kind, file=path,
        line_start=start, line_end=node.end_lineno or node.lineno,
        parent=parent, decorators=decorators, bases=bases, signature=signature,
        fields=fields, language="python",
    )


# -- Regex backend (degraded mode for non-Python languages) -------------------

_CLASS_RE = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:public\s+|abstract\s+|final\s+)*class\s+(\w+)"
    r"(?:\s+extends\s+([\w.<>]+))?(?:\s+implements\s+[\w.,\s<>]+)?"
)
_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)")
_ARROW_RE = re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(")
_ANNOTATION_RE = re.compile(r"^\s*@\w[\w.]*(\(.*)?$")


def _regex_symbols(path: str, text: str, language: str = "") -> list[Symbol]:
    lines = text.splitlines()
    out: list[Symbol] = []
    pending: list[tuple[int, str]] = []  # (lineno, annotation text) awaiting a decl
    class_stack: list[tuple[str, int]] = []  # (name, end_line)

    for i, line in enumerate(lines, start=1):
        while class_stack and i > class_stack[-1][1]:
            class_stack.pop()
        if _ANNOTATION_RE.match(line):
            pending.append((i, line.strip()))
            continue
        m = _CLASS_RE.match(line)
        if m:
            end = _block_end(lines, i)
            sym = _regex_symbol(m.group(1), "class", path, i, end, line, pending,
                                parent=class_stack[-1][0] if class_stack else "", language=language)
            if m.group(2):
                sym.bases.append(m.group(2))
            out.append(sym)
            class_stack.append((m.group(1), end))
            pending = []
            continue
        m = _FUNC_RE.match(line) or _ARROW_RE.match(line)
        if m:
            end = _block_end(lines, i)
            kind = "method" if class_stack else "function"
            out.append(_regex_symbol(m.group(1), kind, path, i, end, line, pending,
                                     parent=class_stack[-1][0] if class_stack else "", language=language))
            pending = []
            continue
        if line.strip() and not line.strip().startswith(("//", "*", "/*")):
            # A non-annotation, non-declaration statement orphans pending annotations
            # unless it looks like a method the simple regexes miss: Java/C# typed
            # methods (`public User create(...)`) or TS/NestJS bare methods
            # (`create(dto: UserDto) {`). The bare form is only trusted when
            # annotations are pending — that context is what disambiguates it
            # from calls and control flow.
            name = _method_name(line) if pending else None
            if name:
                end = _block_end(lines, i)
                out.append(_regex_symbol(name, "method" if class_stack else "function",
                                         path, i, end, line, pending,
                                         parent=class_stack[-1][0] if class_stack else "", language=language))
            pending = []
    return out


_TYPED_METHOD_RE = re.compile(
    r"^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:async\s+)?[\w.<>\[\]]+\s+(\w+)\s*\("
)
_BARE_METHOD_RE = re.compile(r"^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:async\s+)?(\w+)\s*\(")
_NOT_METHOD_NAMES = {"if", "for", "while", "switch", "catch", "return", "throw", "new", "super"}


def _method_name(line: str) -> str | None:
    m = _TYPED_METHOD_RE.match(line) or _BARE_METHOD_RE.match(line)
    if m and m.group(1) not in _NOT_METHOD_NAMES:
        return m.group(1)
    return None


def _regex_symbol(name, kind, path, lineno, end, line, pending, parent, language: str = "") -> Symbol:
    start = min([lineno] + [ln for ln, _ in pending]) if pending else lineno
    return Symbol(
        name=name, kind=kind, file=path, line_start=start, line_end=end,
        parent=parent, decorators=[txt for _, txt in pending],
        signature=line.strip()[:160], language=language,
    )


def _block_end(lines: list[str], start: int, cap: int = 400) -> int:
    """Approximate a declaration's end line by brace balance; fall back to start."""
    depth = 0
    opened = False
    for i in range(start - 1, min(len(lines), start - 1 + cap)):
        depth += lines[i].count("{") - lines[i].count("}")
        if "{" in lines[i]:
            opened = True
        if opened and depth <= 0:
            return i + 1
    return start if not opened else min(len(lines), start + cap)
