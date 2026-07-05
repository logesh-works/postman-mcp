"""The policy gate — turns a gate score into an action.

Thresholds are config (``postman-mcp.json`` → ``confidencePolicy``).
``allow_low_confidence`` mirrors ``config.allowLowConfidence``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

GateAction = Literal["auto", "flag", "needs_approval", "blocked"]


class PolicyConfig(BaseModel):
    auto_threshold: int = 90
    flag_threshold: int = 75
    approval_threshold: int = 50
    allow_low_confidence: bool = False


def gate_action(gate_score: int, *, policy: PolicyConfig | None = None) -> GateAction:
    """Map an endpoint's gate score (``min(existence, path)``) to a sync action.

    Below ``approval_threshold`` is ``blocked`` and stays out of every plan, unless
    ``allow_low_confidence`` opts in — in which case it becomes ``needs_approval``
    instead of disappearing outright, so it can still be synced by naming its uid in
    ``apply(approve=[...])``, never automatically.
    """
    p = policy or PolicyConfig()
    if gate_score >= p.auto_threshold:
        return "auto"
    if gate_score >= p.flag_threshold:
        return "flag"
    if gate_score >= p.approval_threshold:
        return "needs_approval"
    return "needs_approval" if p.allow_low_confidence else "blocked"
