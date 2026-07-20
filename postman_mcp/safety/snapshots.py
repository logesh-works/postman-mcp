"""Collection snapshotting — written before every successful PUT.

A write that cannot be rolled back is not performed: :func:`save_snapshot` is called
by the Executor *before* the PUT, and a snapshot write failure aborts the write.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SNAPSHOTS_DIRNAME = "postman/snapshots"
DEFAULT_RETENTION = 20


def _dir(project_root: Path | str) -> Path:
    d = Path(project_root) / SNAPSHOTS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def save_snapshot(
    collection: dict[str, Any],
    collection_id: str,
    project_root: Path | str = ".",
    *,
    label: Optional[str] = None,
    retention: int = DEFAULT_RETENTION,
) -> str:
    """Atomically persist the pre-write collection state; returns the ``snapshot_id``."""
    snapshot_id = f"{_timestamp()}-{collection_id}"
    if label:
        safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        snapshot_id += f"-{safe_label}"

    path = _dir(project_root) / f"{snapshot_id}.json"
    payload = {
        "snapshot_id": snapshot_id,
        "collection_id": collection_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "collection": collection,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)
    _prune(project_root, collection_id, retention)
    return snapshot_id


def load_snapshot(snapshot_id: str, project_root: Path | str = ".") -> dict[str, Any]:
    path = _dir(project_root) / f"{snapshot_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No snapshot with id {snapshot_id!r}.")
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(
    project_root: Path | str = ".", *, collection_id: Optional[str] = None, limit: int = 20
) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(_dir(project_root).glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if collection_id and data.get("collection_id") != collection_id:
            continue
        entries.append({k: v for k, v in data.items() if k != "collection"})
        if len(entries) >= limit:
            break
    return entries


def _prune(project_root: Path | str, collection_id: str, retention: int) -> None:
    """Keep only the newest ``retention`` snapshots per collection."""
    paths = sorted(
        (p for p in _dir(project_root).glob(f"*-{collection_id}*.json")),
        reverse=True,
    )
    for stale in paths[retention:]:
        stale.unlink(missing_ok=True)
