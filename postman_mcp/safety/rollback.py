"""Rollback — restore a prior snapshot, itself two-phase and itself snapshotted.

Reuses ``postman.merge`` item-key matching to render a readable summary of what a
restore would change, rather than a raw JSON diff.
"""

from __future__ import annotations

from typing import Any

from postman_mcp.postman import merge


def _collect_items(collection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for _, _, item in merge._iter_request_items(collection.get("item", [])):
        key = merge.item_key(item)
        if key:
            items[key] = item
    return items


def diff_rollback(current: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, list[str]]:
    """What restoring ``snapshot`` over ``current`` would change, by route key."""
    cur_items = _collect_items(current)
    snap_items = _collect_items(snapshot)

    would_add = sorted(set(snap_items) - set(cur_items))  # existed in snapshot, gone now
    would_remove = sorted(set(cur_items) - set(snap_items))  # added since the snapshot
    would_change = sorted(
        key for key in set(cur_items) & set(snap_items)
        if cur_items[key] != snap_items[key]
    )
    return {"restore": would_add, "revert_delete": would_remove, "revert_modify": would_change}


def render_rollback_preview(snapshot_id: str, diff: dict[str, list[str]]) -> str:
    lines = [f"ROLLBACK PREVIEW → snapshot {snapshot_id}", ""]
    if diff["restore"]:
        lines.append("Would restore (currently missing):")
        lines.extend(f"  + {k}" for k in diff["restore"])
    if diff["revert_delete"]:
        lines.append("Would remove (added since this snapshot):")
        lines.extend(f"  - {k}" for k in diff["revert_delete"])
    if diff["revert_modify"]:
        lines.append("Would revert (changed since this snapshot):")
        lines.extend(f"  ~ {k}" for k in diff["revert_modify"])
    if not any(diff.values()):
        lines.append("No difference — the live collection already matches this snapshot.")
    lines.append("")
    lines.append("Restore? [y / n]   (nothing writes on n; the current state is snapshotted first)")
    return "\n".join(lines)
