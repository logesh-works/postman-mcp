"""The Graph Witness — an index-sourced, framework-blind alternative to the parser
witness (``witness/engine.py``) for V3-engine repos.

Produces a :class:`~postman_mcp.witness.engine.WitnessSet` from the deterministic
index's mined route candidates instead of framework-specific parsers: lower fidelity
(method + path + a best-effort ``code_ref`` only — no request/response schema, no auth
detection, since the candidate miner deliberately doesn't attempt those), but zero
framework maintenance. It feeds the exact same ``WitnessSet`` -> APIM conversion
(``witness_to_apim``) and the exact same verification cross-checks
(``verify/pipeline.py``) a parser witness does — a drop-in alternative source, not a
parallel pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.index import RepoIndex, build_index
from postman_mcp.index.prefixes import FileLineCache, composed_variants, file_prefix_hints
from postman_mcp.index.symbols import Symbol
from postman_mcp.models import InputSource, RouteModel, normalize_path
from postman_mcp.witness.engine import WitnessSet


def build_graph_witness(
    project_root: Path | str = ".",
    *,
    index: Optional[RepoIndex] = None,
    service: str = "default",
) -> WitnessSet:
    """Mine route candidates from the index and wrap them as a :class:`WitnessSet`.

    Each candidate's raw, locally-declared path is composed with any generic prefix
    hints found on its file (and its importers' mount lines) via
    ``index/prefixes.py`` — the same mechanism ``retrieve/slicer.py`` uses for seed
    resolution. A file can carry hints for mounts that have nothing to do with a
    given candidate (e.g. an app-level route declared in the same file as several
    routers' mount calls), so — deliberately recall-over-precision, matching the
    miner's own design — **every** composed variant is emitted as its own candidate
    route rather than guessing which one hint is "the" match; an unrelated variant
    just becomes a harmless extra entry a comparison would show as graph-only, never
    a route that goes missing. Deduplicates by ``(method, normalized path)`` — the
    same identity key the verification pipeline uses. Verb-less generic-route hits
    (``method == ""``) are too weak to assert a route identity from and are skipped
    here, though they still count for grounding (``verify/candidates.py``).
    """
    root = Path(project_root)
    idx = index or build_index(root)
    graph = idx.graph()
    get_lines = FileLineCache(root)
    hint_cache: dict[str, tuple[set[str], set[str]]] = {}

    seen: set[tuple[str, str]] = set()
    routes: list[RouteModel] = []
    for c in idx.candidates:
        if not c.method:
            continue
        own_hints, importer_hints = hint_cache.setdefault(c.file, file_prefix_hints(graph, get_lines, c.file))
        for composed_path in composed_variants(c.path, own_hints, importer_hints):
            key = (c.method.upper(), normalize_path(composed_path))
            if key in seen:
                continue
            seen.add(key)
            symbol = _enclosing_symbol(idx.symbols, c.file, c.line)
            code_ref = f"{c.file}::{symbol}" if symbol else c.file
            routes.append(
                RouteModel(
                    method=c.method.upper(),
                    path=composed_path,
                    source=InputSource.CODE,
                    code_ref=code_ref,
                    auth_required=False,
                )
            )
    notes = ["graph witness: mined from the index's candidate miner — no schema/auth extraction"]
    return WitnessSet(routes, notes=notes, skipped=[], service=service)


def _enclosing_symbol(symbols: list[Symbol], file: str, line: int) -> Optional[str]:
    """The smallest symbol span in ``file`` containing ``line`` — a best-effort handler name."""
    best: Optional[Symbol] = None
    for sym in symbols:
        if sym.file == file and sym.line_start <= line <= sym.line_end:
            if best is None or (sym.line_end - sym.line_start) < (best.line_end - best.line_start):
                best = sym
    return best.qualname if best else None
