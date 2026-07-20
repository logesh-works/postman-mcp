"""Verification-layer wrapper: which repo class did an endpoint's fact evidence cite?

Kept separate from ``verify/candidates.py`` (which grounds route *identity*
citations) since resolving "what class does this citation point at" is the
distinct primitive ``verify/pipeline.py`` needs before it can ground individual
body/response fields via ``index/fields.py``.
"""

from __future__ import annotations

from typing import Optional

from postman_mcp.contract.schema import Evidence
from postman_mcp.index.graph import RepoGraph
from postman_mcp.index.symbols import Symbol

__all__ = ["resolve_cited_class"]


def resolve_cited_class(graph: RepoGraph, evidence: list[Evidence]) -> Optional[Symbol]:
    """The class ``Symbol`` a fact's own evidence cites, if any.

    Checks every evidence item (a good-faith submission may cite both the
    handler and the DTO), preferring an exact ``Evidence.symbol`` name match,
    else the tightest (smallest-span) class symbol overlapping the cited line
    range. Returns ``None`` (never raises) when nothing resolves — callers must
    degrade to today's behavior, never regress.
    """
    for ev in evidence:
        candidates = [
            s for s in graph.symbols_in(ev.file)
            if s.kind == "class" and not (s.line_end < ev.line_start or s.line_start > ev.line_end)
        ]
        if not candidates:
            continue
        if ev.symbol:
            named = [s for s in candidates if s.name == ev.symbol]
            if named:
                return named[0]
        return min(candidates, key=lambda s: s.line_end - s.line_start)
    return None
