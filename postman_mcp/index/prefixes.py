"""Generic prefix-composition utilities — shared by ``retrieve/slicer.py`` (decorator-
literal seed resolution) and ``verify/graph_witness.py`` (mined-candidate route
identity), so a route's full composed path is computed the same way regardless of
which consumer is asking.

Stays framework-blind by construction: ``prefix``/``base_path``-shaped keyword
literals and a call's first positional string argument are generic vocabulary/shape
across routing ecosystems, never one framework's specific mounting function name
(contrast with ``include_router`` or ``register_blueprint``, which this deliberately
does not name).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

_PREFIX_KW = re.compile(r"""\b\w*(?:prefix|base_path)\s*=\s*["']([^"']*)["']""")
# A call's first positional string argument followed by a comma — the shape of
# `app.use('/api/users', usersRouter)` or `path("users/", include(...))` alike. Noisy
# by nature (an unrelated call can match); it only ever *adds* a composed-path
# candidate that either matches the target or is silently ignored.
_POSITIONAL_PREFIX = re.compile(r"""\(\s*["']([^"']*)["']\s*,""")

GetLines = Callable[[str], Optional[list]]


def file_prefix_hints(graph, get_lines: GetLines, file: str) -> tuple[set[str], set[str]]:
    """Prefix literals for ``file``, split into ``(own_hints, importer_hints)`` so a
    caller can compose *both* levels together (a router's own local prefix AND where
    it's mounted) rather than only ever applying one level — a route registered as
    ``APIRouter(prefix="/users")`` and mounted via
    ``include_router(users.router, prefix="/api/v1")`` needs both to reach its real
    ``/api/v1/users``. ``graph`` is a :class:`~postman_mcp.index.graph.RepoGraph`.
    """
    own: set[str] = set()
    for line in get_lines(file) or []:
        own.update(m.group(1) for m in _PREFIX_KW.finditer(line))
    importer_hints: set[str] = set()
    module_token = Path(file).stem
    for edge in graph.importers_of(file):
        tokens = (set(edge.used_as) | set(edge.names) | {module_token}) - {""}
        for line in get_lines(edge.src) or []:
            if any(tok in line for tok in tokens):
                importer_hints.update(m.group(1) for m in _PREFIX_KW.finditer(line))
                importer_hints.update(m.group(1) for m in _POSITIONAL_PREFIX.finditer(line))
    return own, importer_hints


def _compose(prefix: str, tail: str) -> str:
    if not prefix:
        return tail
    composed = prefix.rstrip("/") + "/" + tail.lstrip("/")
    return composed if composed.startswith("/") else "/" + composed


def composed_variants(lit: str, own_hints: set[str], importer_hints: set[str] = frozenset()) -> set[str]:
    """Every combination of an outer (importer/mount) hint, an inner (own-file) hint,
    and the literal itself — including the literal alone (both hint sets include "").
    """
    variants: set[str] = set()
    for outer in {""} | set(importer_hints):
        for inner in {""} | set(own_hints):
            variants.add((_compose(outer, _compose(inner, lit)).rstrip("/") or "/"))
    return variants


class FileLineCache:
    """Minimal ``file -> lines`` cache for callers that don't already have one
    (``retrieve/slicer.py``'s ``_SourceCache`` plays this role there)."""

    def __init__(self, root: Path):
        self.root = root
        self._cache: dict[str, list[str]] = {}

    def __call__(self, file: str) -> list[str]:
        if file not in self._cache:
            try:
                self._cache[file] = (self.root / file).read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
            except OSError:
                self._cache[file] = []
        return self._cache[file]
