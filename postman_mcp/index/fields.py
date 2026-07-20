"""Field-level grounding — mirrors ``index/candidates.py``'s role, but for claimed
DTO fields instead of route identity: does an LLM-claimed field name on a
request/response body actually exist on the class its evidence cites (own +
inherited)?

Kept separate from ``index/candidates.py`` on purpose: that module is frozen by
policy for route-candidate mining (see ``docs/architecture/v3-proposal.md``); field
grounding is a distinct concern and shouldn't share its churn budget.

Python-only for now: ``Symbol.fields`` is only populated by the ``ast`` backend
(``index/symbols.py``); non-Python symbols always resolve ``fields_of() -> ([], False)``,
so every claim about them lands in ``unknown``, never ``ungrounded`` — no new
coverage, no new false positives, for any other language. Pure static analysis: no
imports, no execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from postman_mcp.index.graph import RepoGraph
from postman_mcp.index.symbols import Symbol

__all__ = ["FieldGroundingResult", "ground_claimed_fields"]


@dataclass
class FieldGroundingResult:
    grounded: set[str] = field(default_factory=set)
    ungrounded: set[str] = field(default_factory=set)  # confidently absent from class + resolved bases
    unknown: set[str] = field(default_factory=set)      # an unresolved (non-inert) base could define it


def ground_claimed_fields(graph: RepoGraph, cls: Symbol, claimed: Iterable[str]) -> FieldGroundingResult:
    """Classify each claimed field name against ``cls``'s own + inherited fields."""
    known, fully_resolved = graph.fields_of(cls)
    known_names = {f.name for f in known}
    result = FieldGroundingResult()
    for name in claimed:
        if not name:
            continue
        if name in known_names:
            result.grounded.add(name)
        elif fully_resolved:
            result.ungrounded.add(name)
        else:
            result.unknown.add(name)
    return result
