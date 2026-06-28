"""Render a :class:`SyncPlan` as the diff preview shown in Claude Code.

The primary view is a markdown table (``Status | Method | Route | Target |
Auth | Body | Response | Source``), so the preview can be scanned at a glance
instead of read line by line. Anything that doesn't fit a cell (low-confidence
warnings, preserved human-owned fields, skipped files) is listed as a short
footnote beneath the table.
"""

from __future__ import annotations

from postman_mcp.models import ChangeType, RequestDiff, SyncPlan

_TAG = {
    ChangeType.NEW: "[NEW]",
    ChangeType.MODIFIED: "[MODIFIED]",
    ChangeType.DEPRECATED: "[DEPRECATED]",
    ChangeType.UNCHANGED: "[UNCHANGED]",
}

_HEADER = ("Status", "Method", "Route", "Target", "Auth", "Body", "Response", "Source")


def _target_cell(into: str) -> str:
    into = (into or "/").strip("/")
    return into or "Root Collection"


def _row(d: RequestDiff) -> tuple[str, ...]:
    return (
        _TAG[d.change],
        d.method,
        d.path,
        _target_cell(d.into),
        d.auth,
        d.body_name,
        d.response_name,
        f"[{d.source.value}]",
    )


def _render_table(rows: list[tuple[str, ...]]) -> str:
    lines = [
        "| " + " | ".join(_HEADER) + " |",
        "|" + "|".join(["---"] * len(_HEADER)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _footnotes(changed: list[RequestDiff]) -> list[str]:
    notes: list[str] = []
    for d in changed:
        if d.low_confidence:
            notes.append(f"  ⚠ {d.method} {d.path}: lower confidence (body inferred, not from a type)")
        if d.preserved:
            notes.append(f"  {d.method} {d.path}, Preserved (human-owned): " + ", ".join(d.preserved))
    return notes


def render_plan(plan: SyncPlan) -> str:
    """Render the full preview for a write-capable command."""
    if not plan.diffs and not plan.skipped:
        return "Nothing to sync. The collection is already up to date with the code."

    blocks: list[str] = []
    target = plan.collection_name or plan.collection_id
    if not plan.is_default_collection:
        blocks.append(
            f"⚠ Target is a NON-DEFAULT collection ({target}). "
            "Re-run with --confirm to allow writing here."
        )

    changed = [d for d in plan.diffs if d.change != ChangeType.UNCHANGED]
    if changed:
        blocks.append(_render_table([_row(d) for d in changed]))

    notes = _footnotes(changed)
    if notes:
        blocks.append("\n".join(notes))

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
    """Render the read-only drift report for ``status``. No write prompt."""
    if not plan.has_changes and not plan.skipped:
        return "No drift. Postman matches the code."

    blocks: list[str] = ["DRIFT CHECK (read-only, nothing will be written)"]
    changed = [d for d in plan.diffs if d.change != ChangeType.UNCHANGED]
    if changed:
        blocks.append(_render_table([_row(d) for d in changed]))

    notes = _footnotes(changed)
    if notes:
        blocks.append("\n".join(notes))

    if plan.skipped:
        blocks.append("Skipped: " + ", ".join(plan.skipped))

    blocks.append(_summary(changed))
    return "\n\n".join(blocks)
