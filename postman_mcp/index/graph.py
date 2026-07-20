"""Import graph + cross-file name resolution.

Import edges are resolved with *language* rules (Python module resolution,
Node relative-path resolution) — stable, specified, framework-free. External
package imports (``fastapi``, ``express``) resolve to nothing on purpose:
the graph only maps code that lives in the repository.

:class:`RepoGraph` is the query surface the retrieval layer uses:
``resolve_name`` (where is the definition of ``UserCreate`` as seen from this
file?) and ``importers_of`` (who mounts this router file?).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from postman_mcp.index.symbols import Symbol, SymbolField

# Base identifiers known, by Python-language convention (not any one framework), to
# contribute no arbitrary data fields of their own beyond what a subclass declares.
# Without this, field grounding is a near-total no-op for the dominant real case
# (Pydantic/dataclass DTOs), since their root base is always external and otherwise
# unresolvable. Narrow and explicit — a deliberate, bounded exception to this
# package's framework-blindness, not a growing list: findings it enables are never
# more than a confidence penalty, never a reject.
_INERT_BASES = {
    "object", "Exception", "BaseException", "Protocol", "Generic", "ABC",
    "BaseModel", "TypedDict", "NamedTuple",
}


@dataclass
class ImportEdge:
    src: str                 # importing file (repo-relative posix)
    dst: str                 # imported file (repo-relative posix)
    names: list[str] = field(default_factory=list)  # imported names, as DEFINED at dst; [] = whole module
    used_as: list[str] = field(default_factory=list)  # same names as REFERENCED in src (honors `as` aliasing)

    def to_doc(self) -> dict:
        return {"src": self.src, "dst": self.dst, "names": self.names, "used_as": self.used_as}

    @classmethod
    def from_doc(cls, d: dict) -> "ImportEdge":
        return cls(src=d["src"], dst=d["dst"], names=d.get("names", []), used_as=d.get("used_as", []))


def extract_imports(path: str, language: str, text: str, repo_files: Iterable[str]) -> list[ImportEdge]:
    files = set(repo_files)
    if language == "python":
        return _python_imports(path, text, files)
    if language in ("typescript", "javascript"):
        return _js_imports(path, text, files)
    return []


# -- Python ------------------------------------------------------------------


def _python_imports(path: str, text: str, files: set[str]) -> list[ImportEdge]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    edges: list[ImportEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                dst = _resolve_module(alias.name, files)
                if dst:
                    edges.append(ImportEdge(src=path, dst=dst, names=[]))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:  # relative import: walk up from the importing package
                base_parts = path.split("/")[:-1]
                up = node.level - 1
                if up:
                    base_parts = base_parts[: len(base_parts) - up] if up <= len(base_parts) else []
                module = ".".join([p for p in base_parts if p] + ([module] if module else [])).replace("/", ".")
            dst = _resolve_module(module, files)
            names = [a.name for a in node.names if a.name != "*"]
            used_as = [(a.asname or a.name) for a in node.names if a.name != "*"]
            if dst:
                edges.append(ImportEdge(src=path, dst=dst, names=names, used_as=used_as))
            # Whether or not the base module resolved, each imported name may itself be
            # a submodule (`from routers import users` — a package-then-submodule style
            # at least as common as `from routers.users import router`). Try both; a
            # submodule that also resolves gets its own edge alongside the package edge.
            if dst is None or dst.endswith("__init__.py"):
                for a in node.names:
                    sub = _resolve_module(f"{module}.{a.name}" if module else a.name, files)
                    if sub:
                        edges.append(ImportEdge(src=path, dst=sub, names=[], used_as=[a.asname or a.name]))
    return edges


def _resolve_module(dotted: str, files: set[str]) -> Optional[str]:
    """Map ``app.routers.users`` to a repo file, trying common source roots."""
    if not dotted:
        return None
    rel = dotted.replace(".", "/")
    for prefix in ("", "src/", "app/", "lib/"):
        for candidate in (f"{prefix}{rel}.py", f"{prefix}{rel}/__init__.py"):
            if candidate in files:
                return candidate
    return None


# -- JavaScript / TypeScript ---------------------------------------------------

_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?P<clause>[\w{}\s,*$]+?)\s+from\s+|import\s*\(\s*|require\s*\(\s*|export\s+[\w{}\s,*$]+?\s+from\s+)['"](?P<spec>[^'"]+)['"]"""
)
_JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _js_imports(path: str, text: str, files: set[str]) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    src_dir = "/".join(path.split("/")[:-1])
    for m in _JS_IMPORT_RE.finditer(text):
        spec = m.group("spec")
        if not spec.startswith("."):
            continue  # external package
        target = _normalize_rel(src_dir, spec)
        dst = None
        for candidate in [target + ext for ext in _JS_EXTS] + [f"{target}/index{ext}" for ext in _JS_EXTS] + [target]:
            if candidate in files:
                dst = candidate
                break
        if not dst:
            continue
        clause = m.group("clause") or ""
        names = re.findall(r"\w+", clause.split("from")[0]) if clause else []
        edges.append(ImportEdge(src=path, dst=dst, names=[n for n in names if n not in ("import", "as", "default")]))
    return edges


def _normalize_rel(src_dir: str, spec: str) -> str:
    parts = (src_dir.split("/") if src_dir else []) + spec.split("/")
    out: list[str] = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if out:
                out.pop()
        else:
            out.append(p)
    return "/".join(out)


# -- Query surface -------------------------------------------------------------


class RepoGraph:
    """Symbol + import lookups the retrieval slicer runs on."""

    def __init__(self, symbols: list[Symbol], imports: list[ImportEdge]):
        self.symbols = symbols
        self.imports = imports
        self._by_file: dict[str, list[Symbol]] = {}
        self._by_name: dict[str, list[Symbol]] = {}
        for s in symbols:
            self._by_file.setdefault(s.file, []).append(s)
            self._by_name.setdefault(s.name, []).append(s)
        self._out: dict[str, list[ImportEdge]] = {}
        self._in: dict[str, list[ImportEdge]] = {}
        for e in imports:
            self._out.setdefault(e.src, []).append(e)
            self._in.setdefault(e.dst, []).append(e)

    def symbols_in(self, file: str) -> list[Symbol]:
        return self._by_file.get(file, [])

    def by_name(self, name: str) -> list[Symbol]:
        return self._by_name.get(name, [])

    def importers_of(self, file: str) -> list[ImportEdge]:
        return self._in.get(file, [])

    def resolve_name(self, name: str, from_file: str) -> Optional[Symbol]:
        """Definition of ``name`` as seen from ``from_file``.

        Order: same-file definition → explicitly imported name → import of a
        module that defines it → unique repo-wide definition. Ambiguity
        (multiple non-imported candidates) resolves to None rather than a guess.
        """
        for s in self._by_file.get(from_file, []):
            if s.name == name and not s.parent:
                return s
        for e in self._out.get(from_file, []):
            if name in e.names:
                for s in self._by_file.get(e.dst, []):
                    if s.name == name and not s.parent:
                        return s
        for e in self._out.get(from_file, []):
            if not e.names:
                for s in self._by_file.get(e.dst, []):
                    if s.name == name and not s.parent:
                        return s
        candidates = [s for s in self._by_name.get(name, []) if not s.parent]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def fields_of(self, symbol: Symbol) -> tuple[list[SymbolField], bool]:
        """Own + inherited fields for a class ``Symbol``, walking ``bases`` via
        ``resolve_name``.

        Returns ``(fields, fully_resolved)``. ``fully_resolved`` is ``False``
        whenever any base in the chain is neither resolvable in-repo nor a
        known-inert terminal (``_INERT_BASES``) — callers must treat "field not
        found" as *unknown* in that case, never as *ungrounded*, mirroring the
        "widens, never narrows" posture ``index/candidates.py`` already uses for
        identity grounding. Always ``([], False)`` for a non-Python symbol: field
        extraction is Python-only for now (see ``Symbol.language``), so an absent
        field there is "not captured," never "confirmed absent."
        """
        return self._fields_of(symbol, seen=set())

    def _fields_of(self, symbol: Symbol, seen: set[tuple[str, str]]) -> tuple[list[SymbolField], bool]:
        if symbol.language != "python":
            return [], False
        key = (symbol.file, symbol.qualname)
        if key in seen:
            return [], True
        seen.add(key)
        fields = list(symbol.fields)
        known_names = {f.name for f in fields}
        fully_resolved = True
        for base_expr in symbol.bases:
            base_name = base_expr.split("[", 1)[0].rsplit(".", 1)[-1]
            base_sym = self.resolve_name(base_name, symbol.file)
            if base_sym is None:
                if base_name not in _INERT_BASES:
                    fully_resolved = False
                continue
            base_fields, base_ok = self._fields_of(base_sym, seen)
            for f in base_fields:
                if f.name not in known_names:
                    fields.append(f)
                    known_names.add(f.name)
            fully_resolved = fully_resolved and base_ok
        return fields, fully_resolved
