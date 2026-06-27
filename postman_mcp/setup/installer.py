"""Install bundled slash-command markdown into ``.claude/commands/postman/``.

Each ``commands/*.md`` is a thin Claude Code slash command whose body invokes the
matching MCP tool. Copying them into ``.claude/commands/postman/`` is what makes
``/postman:syncapi`` etc. appear — the ``postman:`` namespace comes from the folder.
``init`` re-copies on every run so package upgrades propagate.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# The six in-Claude-Code commands. init/doctor are terminal-only.
COMMAND_NAMES = ("syncapi", "syncchanges", "sync", "syncall", "createenv", "status")

_BUNDLED_DIR = Path(__file__).resolve().parent.parent / "commands"


def commands_dir(project_root: Path | str = ".") -> Path:
    return Path(project_root) / ".claude" / "commands" / "postman"


def install_slash_commands(project_root: Path | str = ".") -> list[Path]:
    """Copy bundled command md files into the project; returns installed paths."""
    target = commands_dir(project_root)
    target.mkdir(parents=True, exist_ok=True)
    installed: list[Path] = []
    for name in COMMAND_NAMES:
        src = _BUNDLED_DIR / f"{name}.md"
        dst = target / f"{name}.md"
        shutil.copyfile(src, dst)
        installed.append(dst)
    return installed


def slash_commands_present(project_root: Path | str = ".") -> bool:
    """Doctor check #5 — all six md files exist under the commands dir."""
    target = commands_dir(project_root)
    return all((target / f"{name}.md").exists() for name in COMMAND_NAMES)
