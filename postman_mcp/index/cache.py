"""Content-addressed index persistence under ``postman/index/``.

The cache document is the serialized :class:`~postman_mcp.index.RepoIndex`.
Freshness is judged per file by SHA-256 (computed by the scanner), so the
builder can reuse symbols/imports/corpus for unchanged files and re-extract
only what actually changed. A corrupt or version-mismatched cache is treated
as absent, never as an error — the index is always rebuildable from source.
"""

from __future__ import annotations

import json
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
    path = cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    return path
