"""Register the MCP server with Claude Code.

``init`` writes the project-scoped ``.mcp.json`` entry directly — deterministic, works
whether or not the ``claude`` CLI is on PATH — and additionally calls ``claude mcp add``
when the CLI is available. Also keeps ``.gitignore`` covering this tool's internal
``postman/`` cache/state paths (never ``postman/config.json`` or ``postman/sync/``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from postman_mcp.config.store import SECRET_FILENAME

MCP_CONFIG_FILENAME = ".mcp.json"
SERVER_NAME = "postman-mcp"

# The entry that launches the stdio server.
_SERVER_ENTRY: dict[str, Any] = {
    "command": "postman-mcp",
    "args": ["serve"],
    "cwd": "${workspaceFolder}",
}


def _mcp_config_path(project_root: Path | str) -> Path:
    return Path(project_root) / MCP_CONFIG_FILENAME


def register_mcp_server(project_root: Path | str = ".") -> Path:
    """Add/refresh the ``postman-mcp`` server in project ``.mcp.json`` (idempotent)."""
    path = _mcp_config_path(project_root)
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    servers = data.setdefault("mcpServers", {})
    servers[SERVER_NAME] = dict(_SERVER_ENTRY)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Best-effort: also register via the Claude CLI if present.
    if shutil.which("claude"):
        try:  # pragma: no cover - depends on external CLI
            subprocess.run(
                ["claude", "mcp", "add", SERVER_NAME, "postman-mcp", "serve"],
                cwd=str(project_root),
                capture_output=True,
                timeout=15,
            )
        except Exception:
            pass  # .mcp.json is the source of truth; CLI is a bonus.
    return path


def is_server_registered(project_root: Path | str = ".") -> bool:
    """Doctor check #4 — server present in ``.mcp.json``."""
    path = _mcp_config_path(project_root)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return SERVER_NAME in data.get("mcpServers", {})


# Everything under postman/ except config.json and sync/ is this tool's internal
# cache/state (index, models, plans, snapshots, audit log, the API key file) — never
# meant to be committed. postman/config.json and postman/sync/ are deliberately left
# out so they stay tracked.
_GITIGNORE_LINES = [
    SECRET_FILENAME,
    "postman/index/",
    "postman/models/",
    "postman/plans/",
    "postman/snapshots/",
    "postman/audit.jsonl",
]


def ensure_gitignore(project_root: Path | str = ".") -> None:
    """Ensure this tool's internal ``postman/`` cache/state paths are gitignored."""
    path = Path(project_root) / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_lines = set(existing.splitlines())
    missing = [line for line in _GITIGNORE_LINES if line not in existing_lines]
    if not missing:
        return
    prefix = "" if existing.endswith("\n") or not existing else "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + "\n".join(missing) + "\n")
