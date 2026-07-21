"""Content-addressed index persistence under ``postman/index/``.

The cache document is the serialized :class:`~postman_mcp.index.RepoIndex`.
Freshness is judged per file by SHA-256 (computed by the scanner), so the
builder can reuse symbols/imports/corpus for unchanged files and re-extract
only what actually changed. A corrupt or version-mismatched cache is treated
as absent, never as an error — the index is always rebuildable from source.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Optional

CACHE_DIR = "postman/index"
CACHE_FILE = "index.json"


def cache_path(root: Path | str) -> Path:
    return Path(root) / CACHE_DIR / CACHE_FILE


def load_cached_doc(root: Path | str) -> Optional[dict]:
    path = cache_path(root)
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def save_doc(root: Path | str, doc: dict) -> Path:
    """Write the cache document atomically.

    A build that's interrupted or killed mid-write must never leave a
    truncated/corrupt cache file behind — that would silently discard
    whatever was already indexed, on top of whatever caused the
    interruption. Write to a uniquely-named temp file in the same
    directory (so the final ``os.replace`` is same-filesystem and atomic
    on both POSIX and Windows), then swap it in; the old file (if any)
    stays fully intact right up until the swap.
    """
    path = cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        tmp_path.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)  # no-op once replace() has moved it
    return path
