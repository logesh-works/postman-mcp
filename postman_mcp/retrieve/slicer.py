"""Graph slicing — from a target to the minimal set of symbol-aligned chunks.

Given a target (a symbol, a file, or ``"METHOD /path"``), the slicer walks the
repo graph outward from the seed symbols and collects, in priority rank:

- rank 0 — the seed symbols themselves (decorators included)
- rank 1 — the *type closure*: classes referenced from the seed, recursively
  (DTOs, serializers, nested models, base classes), depth-limited
- rank 2 — functions the seed calls that are defined elsewhere in the repo
  (service layer), one hop
- rank 3 — the *mount chain*: lines in files that import the seed's file and
  mention its exported names (router registration, prefixes)
- rank 4 — corpus witnesses (test URLs, ``.http`` entries) matching the target

Chunks are whole symbols, never windowed splits — a Pydantic model cut in half
is worth nothing to the model reading it. Everything here is name-and-graph
mechanics; no route semantics, no framework knowledge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from postman_mcp.index import RepoIndex
from postman_mcp.index.corpus import HTTP_METHODS, CorpusEntry
from postman_mcp.index.graph import RepoGraph
from postman_mcp.index.prefixes import composed_variants, file_prefix_hints
from postman_mcp.index.symbols import Symbol

_HANDLER_REF = re.compile(r",\s*([A-Za-z_]\w*)\s*\)\s*;?\s*$")

TYPE_CLOSURE_DEPTH = 3
_TYPE_NAME = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\b")
_CALL_NAME = re.compile(r"\b([a-z_][a-z0-9_]{2,})\s*\(")
_METHOD_PATH_TARGET = re.compile(rf"^({'|'.join(HTTP_METHODS)})\s+(/\S*)$", re.IGNORECASE)

# Common language/stdlib-ish capitalized tokens that are never worth resolving.
_TYPE_STOPWORDS = {
    "True", "False", "None", "Optional", "List", "Dict", "Set", "Tuple", "Union",
    "Any", "Callable", "Type", "String", "Number", "Boolean", "Promise", "Array",
    "Object", "Depends", "Field", "BaseModel", "Enum", "Exception", "Error",
}


@dataclass
class Chunk:
    file: str
    line_start: int
    line_end: int
    role: str      # "seed" | "type" | "call" | "mount" | "witness"
    rank: int
    text: str

    @property
    def header(self) -> str:
        return f"## {self.file}:{self.line_start}-{self.line_end} [{self.role}]"


class SliceError(Exception):
    """Raised when a target cannot be resolved to any seed symbol."""


def slice_target(index: RepoIndex, root: Path, target: str) -> list[Chunk]:
    graph = index.graph()
    sources = _SourceCache(root)
    target = target.strip()
    seeds = _resolve_seeds(index, graph, sources, target)

    chunks: list[Chunk] = []
    seen: set[tuple[str, int]] = set()

    m = _METHOD_PATH_TARGET.match(target)
    if not seeds and m:
        # Symbol/decorator extraction sees nothing (e.g. a plain call-based
        # registration like Express's `router.get(path, handler)`, which is not a
        # declaration). Fall back to the framework-blind candidate miner: it already
        # matched this exact verb+path shape, so use its hit as the seed span and
        # try to resolve a trailing handler-reference name into a real symbol.
        cand_chunks, handler_syms = _candidate_seeds(index, sources, m.group(1), m.group(2))
        for ch in cand_chunks:
            key = (ch.file, ch.line_start)
            if key not in seen:
                seen.add(key)
                chunks.append(ch)
        seeds = handler_syms

    if not seeds and not chunks:
        raise SliceError(
            f"Could not resolve {target!r} to any symbol. Try a function name, "
            f"'path/to/file.py', 'file.py::symbol', or 'METHOD /path'."
        )

    def add(sym: Symbol, role: str, rank: int) -> Optional[str]:
        key = (sym.file, sym.line_start)
        if key in seen:
            return None
        seen.add(key)
        text = sources.lines(sym.file, sym.line_start, sym.line_end)
        if text is None:
            return None
        chunks.append(Chunk(sym.file, sym.line_start, sym.line_end, role, rank, text))
        return text

    for seed in seeds:
        text = add(seed, "seed", 0)
        if text is None:
            continue
        _expand_types(graph, sources, seed.file, text, add, depth=TYPE_CLOSURE_DEPTH)
        _expand_calls(graph, sources, seed, text, add)

    chunks.extend(_mount_chain(graph, sources, seeds, seen))
    chunks.extend(_witnesses(index, target, seeds))
    return chunks


# -- seed resolution -----------------------------------------------------------


def _resolve_seeds(index: RepoIndex, graph: RepoGraph, sources: "_SourceCache", target: str) -> list[Symbol]:
    m = _METHOD_PATH_TARGET.match(target)
    if m:
        return _seeds_for_path(graph, sources, m.group(2))
    if "::" in target:
        file, _, name = target.partition("::")
        file = file.replace("\\", "/")
        return [s for s in graph.symbols_in(file) if s.name == name] or []
    if "/" in target or "\\" in target or Path(target).suffix:
        file = target.replace("\\", "/")
        symbols = graph.symbols_in(file)
        decorated = [s for s in symbols if s.decorators]
        return decorated or [s for s in symbols if not s.parent]
    named = [s for s in graph.by_name(target) if not s.parent] or graph.by_name(target)
    return named


def _candidate_seeds(
    index: RepoIndex, sources: "_SourceCache", method: str, path: str
) -> tuple[list[Chunk], list[Symbol]]:
    """Fallback seeding from the framework-blind candidate miner (index/candidates.py)
    for call-based registrations symbol extraction cannot see as a declaration."""
    path_norm = path.rstrip("/") or "/"
    wildcard = re.sub(r"\{[^}]+\}|<[^>]+>|:[A-Za-z_]\w*", "*", path_norm)
    graph = index.graph()
    chunks: list[Chunk] = []
    handler_syms: list[Symbol] = []
    for c in index.candidates:
        if c.method and method and c.method != method.upper():
            continue
        c_norm = c.path.rstrip("/") or "/"
        c_wild = re.sub(r"\{[^}]+\}|<[^>]+>|:[A-Za-z_]\w*", "*", c_norm)
        if not (
            c_norm == path_norm or c_wild == wildcard
            or path_norm.endswith(c_norm) or c_norm.endswith(path_norm)
        ):
            continue
        all_lines = sources.all_lines(c.file)
        if all_lines is None:
            continue
        start, end = max(1, c.line - 3), min(len(all_lines), c.line + 3)
        chunks.append(Chunk(c.file, start, end, "seed", 0, "\n".join(all_lines[start - 1: end])))
        m = _HANDLER_REF.search(c.quote)
        if m:
            handler_syms.extend(graph.by_name(m.group(1)))
    return chunks, handler_syms


def _seeds_for_path(graph: RepoGraph, sources: "_SourceCache", path: str) -> list[Symbol]:
    """Symbols whose decorator text (alone, or composed with a generic prefix hint —
    see :func:`postman_mcp.index.prefixes.file_prefix_hints`) matches the path: exact,
    then suffix, then fuzzy.
    """
    path = path.rstrip("/") or "/"
    wildcard = re.sub(r"\{[^}]+\}|<[^>]+>|:[A-Za-z_]\w*", "*", path)
    exact, suffix, fuzzy = [], [], []
    hint_cache: dict[str, tuple[set[str], set[str]]] = {}

    for sym in graph.symbols:
        best: Optional[str] = None
        for dec in sym.decorators:
            if best == "exact":
                break
            for lit in re.findall(r"""["']([^"']*)["']""", dec):
                own_hints, importer_hints = hint_cache.setdefault(
                    sym.file, file_prefix_hints(graph, sources.all_lines, sym.file)
                )
                for lit_norm in composed_variants(lit, own_hints, importer_hints):
                    lit_wild = re.sub(r"\{[^}]+\}|<[^>]+>|:[A-Za-z_]\w*", "*", lit_norm)
                    if lit_norm == path or lit_wild == wildcard:
                        best = "exact"
                        break
                    if best is None and lit_norm and (path.endswith(lit_norm) or (lit_wild and wildcard.endswith(lit_wild))):
                        best = "suffix"
                    elif best is None and len(lit_norm) > 1 and lit_norm in path:
                        best = "fuzzy"
                if best == "exact":
                    break
        if best == "exact":
            exact.append(sym)
        elif best == "suffix":
            suffix.append(sym)
        elif best == "fuzzy":
            fuzzy.append(sym)
    return exact or suffix or fuzzy


# -- expansion -----------------------------------------------------------------


def _expand_types(graph, sources, from_file, text, add, depth) -> None:
    if depth <= 0:
        return
    for name in dict.fromkeys(_TYPE_NAME.findall(text)):  # ordered, deduped
        if name in _TYPE_STOPWORDS:
            continue
        sym = graph.resolve_name(name, from_file)
        if sym is None or sym.kind != "class":
            continue
        body = add(sym, "type", 1)
        if body is not None:
            _expand_types(graph, sources, sym.file, body, add, depth - 1)


def _expand_calls(graph, sources, seed: Symbol, text: str, add) -> None:
    for name in dict.fromkeys(_CALL_NAME.findall(text)):
        if name == seed.name:
            continue
        sym = graph.resolve_name(name, seed.file)
        if sym is None or sym.kind != "function" or sym.file == seed.file:
            continue
        add(sym, "call", 2)


def _mount_chain(graph: RepoGraph, sources: "_SourceCache", seeds: list[Symbol], seen) -> list[Chunk]:
    """Lines in importer files that mention the seed file's imported names."""
    chunks: list[Chunk] = []
    for file in dict.fromkeys(s.file for s in seeds):
        exported = {s.name for s in graph.symbols_in(file)}
        module_token = Path(file).stem
        for edge in graph.importers_of(file):
            # `used_as` is what the mounting call actually writes (honors `as`
            # aliasing); exported symbol names and the module stem catch the rest.
            tokens = set(edge.used_as) | set(edge.names) | (set(edge.names) & exported) | {module_token}
            all_lines = sources.all_lines(edge.src)
            if all_lines is None:
                continue
            hits = [
                i + 1 for i, line in enumerate(all_lines)
                if any(tok in line for tok in tokens)
            ]
            for start, end in _merge_windows(hits, len(all_lines), pad=3):
                key = (edge.src, start)
                if key in seen:
                    continue
                seen.add(key)
                text = "\n".join(all_lines[start - 1: end])
                chunks.append(Chunk(edge.src, start, end, "mount", 3, text))
    return chunks


def _witnesses(index: RepoIndex, target: str, seeds: list[Symbol]) -> list[Chunk]:
    m = _METHOD_PATH_TARGET.match(target.strip())
    needles = {s.name for s in seeds}
    path_needle = m.group(2).rstrip("/") if m else None
    out: list[Chunk] = []
    for entry in index.corpus:
        match = False
        if path_needle and entry.path and (
            entry.path.rstrip("/") == path_needle or entry.path.rstrip("/").endswith(path_needle)
            or path_needle.endswith(entry.path.rstrip("/"))
        ):
            match = True
        if not match and entry.path and any(f"/{n}" in entry.path or n in entry.path for n in needles if len(n) > 4):
            match = True
        if match:
            line = f"{entry.kind}: {entry.method or '?'} {entry.path}  ({entry.file}:{entry.line})"
            out.append(Chunk(entry.file, entry.line, entry.line, "witness", 4, line))
    return out[:12]


def _merge_windows(hits: list[int], total: int, pad: int) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    for h in hits:
        start, end = max(1, h - pad), min(total, h + pad)
        if windows and start <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], end)
        else:
            windows.append((start, end))
    return windows


# -- source access ---------------------------------------------------------------


class _SourceCache:
    def __init__(self, root: Path):
        self.root = root
        self._files: dict[str, Optional[list[str]]] = {}

    def all_lines(self, file: str) -> Optional[list[str]]:
        if file not in self._files:
            try:
                self._files[file] = (self.root / file).read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except OSError:
                self._files[file] = None
        return self._files[file]

    def lines(self, file: str, start: int, end: int) -> Optional[str]:
        all_lines = self.all_lines(file)
        if all_lines is None:
            return None
        return "\n".join(all_lines[start - 1: end])
