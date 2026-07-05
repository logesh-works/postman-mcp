"""Render a :class:`PlanDocument` as the diff preview — the extended diff renderer.

Extends the existing table format (``diff/render.py``) with a confidence/provenance
column, a separate needs-approval section, and rejected/blocked footers — so a reviewer
sees not just *what* changed but *how sure* the system is about each row.
"""

from __future__ import annotations

from postman_mcp.confidence.scorer import gate_score
from postman_mcp.models import ChangeType, RequestDiff
from postman_mcp.plan.compiler import PlanDocument

_TAG = {
    ChangeType.NEW: "[NEW]",
    ChangeType.MODIFIED: "[MODIFIED]",
    ChangeType.DEPRECATED: "[DEPRECATED]",
    ChangeType.UNCHANGED: "[UNCHANGED]",
}

_HEADER = ("Status", "Method", "Route", "Target", "Auth", "Body", "Response", "Confidence", "Source")


def _confidence_cell(confidence: dict[str, int], gate: str) -> str:
    score = gate_score(confidence) if confidence else 0
    marker = {"auto": "✓", "flag": "◐", "needs_approval": "⚠"}.get(gate, "?")
    return f"{score} {marker}"


def _target_cell(into: str) -> str:
    into = (into or "/").strip("/")
    return into or "Root Collection"


def render_plan_preview(
    doc: PlanDocument, *, collection_name: str | None = None
) -> str:
    if not doc.entries and not doc.rejected and not doc.blocked_uids:
        return "Nothing to sync. The collection is already up to date with the model."

    blocks: list[str] = []
    syncable = [e for e in doc.entries if e.gate_action in ("auto", "flag")]
    approval = [e for e in doc.entries if e.gate_action == "needs_approval"]

    rows = []
    for entry in syncable:
        d = RequestDiff.model_validate(entry.diff)
        if d.change == ChangeType.UNCHANGED:
            continue
        rows.append((
            _TAG[d.change], d.method, d.path, _target_cell(entry.into), d.auth,
            d.body_name, d.response_name, _confidence_cell(entry.confidence, entry.gate_action),
            f"[{d.source.value}]",
        ))
    if rows:
        lines = ["| " + " | ".join(_HEADER) + " |", "|" + "|".join(["---"] * len(_HEADER)) + "|"]
        lines.extend("| " + " | ".join(r) + " |" for r in rows)
        blocks.append("\n".join(lines))

    if approval:
        blocks.append("NEEDS APPROVAL (confidence below the auto-sync threshold):")
        for entry in approval:
            d = RequestDiff.model_validate(entry.diff)
            score = gate_score(entry.confidence)
            weakest = min(entry.confidence, key=entry.confidence.get) if entry.confidence else "?"
            blocks.append(
                f"  ⚠ {d.method} {d.path} — score {score} (weakest: {weakest})."
                f" Approve with apply(plan_id, approve=[{entry.uid!r}])."
            )

    if doc.rejected:
        blocks.append("Rejected by verification (not shown as changes):")
        for r in doc.rejected:
            reason = r["reasons"][0] if r["reasons"] else r["verdict"]
            blocks.append(f"  ✗ {r['uid']} — {reason}")

    if doc.blocked_uids:
        blocks.append(
            "Blocked (confidence below the approval floor; set allowLowConfidence to override): "
            + ", ".join(doc.blocked_uids)
        )

    new_n = sum(1 for e in syncable if RequestDiff.model_validate(e.diff).change == ChangeType.NEW)
    mod_n = sum(1 for e in syncable if RequestDiff.model_validate(e.diff).change == ChangeType.MODIFIED)
    blocks.append(f"Summary: {new_n} new · {mod_n} modified · {len(approval)} awaiting approval")
    blocks.append(f"plan_id: {doc.plan_id}")
    blocks.append("Write? apply(plan_id, confirm=True)   (nothing writes without it)")
    return "\n\n".join(blocks)
