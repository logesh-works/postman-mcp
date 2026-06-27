"""Render a :class:`SyncPlan` as the diff preview shown in Claude Code.

Every write is preceded by this. Modified requests list anything **preserved**
(human-owned scripts/examples); each request is tagged with its source
``[openapi]``/``[code]`` so lower-confidence routes are visible.
"""

from __future__ import annotations

from postman_mcp.models import ChangeType, RequestDiff, SyncPlan

_TAG = {
    ChangeType.NEW: "[NEW]",
    ChangeType.MODIFIED: "[MODIFIED]",
    ChangeType.DEPRECATED: "[DEPRECATED]",
    ChangeType.UNCHANGED: "[UNCHANGED]",
}


def _render_request(d: RequestDiff) -> str:
    into = d.into if d.into and d.into != "/" else "(root)"
    src = f"[{d.source.value}]"
    conf = "  ⚠ lower confidence" if d.low_confidence else ""
    header = (
        f"SYNC PREVIEW — {d.method} {d.path}  →  collection / {into}   "
        f"{_TAG[d.change]} {src}{conf}"
    )
    lines = [header, ""]
    lines.extend("  " + ln for ln in d.lines)
    if d.preserved:
        lines.append("")
        lines.append("  Preserved (human-owned): " + ", ".join(d.preserved))
    return "\n".join(lines)


def render_plan(plan: SyncPlan) -> str:
    """Render the full preview for a write-capable command."""
    if not plan.diffs and not plan.skipped:
        return "Nothing to sync — the collection is already up to date with the code."

    blocks: list[str] = []
    target = plan.collection_name or plan.collection_id
    if not plan.is_default_collection:
        blocks.append(
            f"⚠ Target is a NON-DEFAULT collection ({target}). "
            "Re-run with --confirm to allow writing here."
        )

    changed = [d for d in plan.diffs if d.change != ChangeType.UNCHANGED]
    for d in changed:
        blocks.append(_render_request(d))

    if plan.skipped:
        blocks.append(
            "Skipped (parse failures, reported and continued):\n  - "
            + "\n  - ".join(plan.skipped)
        )

    summary = _summary(changed)
    blocks.append(summary)
    blocks.append("Write? [y / n]   (nothing writes on n)")
    return "\n\n".join(blocks)


def _summary(changed: list[RequestDiff]) -> str:
    new = sum(1 for d in changed if d.change is ChangeType.NEW)
    mod = sum(1 for d in changed if d.change is ChangeType.MODIFIED)
    dep = sum(1 for d in changed if d.change is ChangeType.DEPRECATED)
    return f"Summary: {new} new · {mod} modified · {dep} deprecated"


def render_status(plan: SyncPlan) -> str:
    """Render the read-only drift report for ``status`` — no write prompt."""
    if not plan.has_changes and not plan.skipped:
        return "No drift — Postman matches the code."
    blocks: list[str] = ["DRIFT CHECK (read-only — nothing will be written)\n"]
    for d in plan.diffs:
        if d.change is ChangeType.UNCHANGED:
            continue
        into = d.into if d.into and d.into != "/" else "(root)"
        blocks.append(
            f"  {_TAG[d.change]:<13} {d.method} {d.path}  →  {into}  [{d.source.value}]"
        )
    if plan.skipped:
        blocks.append("\n  Skipped: " + ", ".join(plan.skipped))
    changed = [d for d in plan.diffs if d.change != ChangeType.UNCHANGED]
    blocks.append("\n" + _summary(changed))
    return "\n".join(blocks)
