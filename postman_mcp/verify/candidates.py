"""The candidate miner (verification usage) — see ``docs/architecture/v3-proposal.md``.

Re-exports the framework-blind mining primitive from ``index/candidates.py`` and adds
the verification-specific grounding check the pipeline uses: does a submitted model's
cited evidence span correspond to a real decorated symbol or a mined route candidate,
independent of any framework-token list? Frozen by policy, per the proposal: recall
improvements belong in retrieval/context, never in new per-framework rules here.
"""

from __future__ import annotations

from postman_mcp.index import RepoIndex
from postman_mcp.index.candidates import RouteCandidate, is_grounded_span, mine_file_candidates

__all__ = ["RouteCandidate", "mine_file_candidates", "is_grounded_span", "is_grounded_evidence"]


def is_grounded_evidence(index: RepoIndex, file: str, line_start: int, line_end: int) -> bool:
    """Is this citation grounded in the repo's own structure — a decorated symbol or a
    mined route candidate at that exact span — independent of any framework token list?
    """
    return is_grounded_span(index.symbols, index.candidates, file, line_start, line_end)
