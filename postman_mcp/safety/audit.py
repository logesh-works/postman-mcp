"""Append-only audit log — one JSON line per lifecycle event.

Fsync'd before the caller proceeds so an audit-log failure can gate a write (the
Executor appends the ``apply`` event, including its outcome, and a snapshot-write
failure is itself an audit entry before the write is refused).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

AUDIT_FILENAME = "postman/audit.jsonl"


def _path(project_root: Path | str) -> Path:
    p = Path(project_root) / AUDIT_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append_event(
    project_root: Path | str,
    event: str,
    *,
    actor: Optional[str] = None,
    model_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    endpoints: Optional[dict[str, int]] = None,
    outcome: str = "ok",
    detail: Optional[dict[str, Any]] = None,
) -> None:
    """Append one audit-log entry. Never mutates or removes prior entries."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        "model_id": model_id,
        "plan_id": plan_id,
        "snapshot_id": snapshot_id,
        "collection_id": collection_id,
        "endpoints": endpoints or {},
        "outcome": outcome,
        "detail": detail or {},
    }
    path = _path(project_root)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_events(project_root: Path | str = ".", *, last: int = 20) -> list[dict[str, Any]]:
    path = _path(project_root)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-last:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
