"""Token estimation + budget fitting for context bundles.

Estimation is the standard chars/4 heuristic — close enough for budgeting,
biased slightly high for code (which tokenizes denser than prose), which errs
on the safe side of the budget.

Fitting is rank-then-size: chunks are grouped by rank (0 = seed, ascending =
less essential) and admitted rank-by-rank; within a rank, smaller chunks first
so one huge model file cannot crowd out three small DTOs. Rank 0 is always
kept even if it alone exceeds the budget — a bundle without its seed is
useless at any price.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from postman_mcp.retrieve.slicer import Chunk

CHARS_PER_TOKEN = 4
MIN_BUDGET = 500
DEFAULT_BUDGET = 8000


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def fit(chunks: list["Chunk"], budget: int) -> tuple[list["Chunk"], list["Chunk"]]:
    """Split ``chunks`` into (kept, omitted) under ``budget`` estimated tokens."""
    budget = max(budget, MIN_BUDGET)
    kept: list["Chunk"] = []
    omitted: list["Chunk"] = []
    used = 0
    by_rank: dict[int, list["Chunk"]] = {}
    for c in chunks:
        by_rank.setdefault(c.rank, []).append(c)
    for rank in sorted(by_rank):
        for chunk in sorted(by_rank[rank], key=lambda c: len(c.text)):
            cost = estimate_tokens(chunk.text) + 8  # header overhead
            if rank == 0 or used + cost <= budget:
                kept.append(chunk)
                used += cost
            else:
                omitted.append(chunk)
    kept.sort(key=lambda c: (c.rank, c.file, c.line_start))
    return kept, omitted
