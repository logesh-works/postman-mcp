"""File inventory — git-aware, ignore-aware, language-tagged, content-hashed.

Prefers ``git ls-files`` (which honors ``.gitignore`` exactly); falls back to a
filesystem walk with a conservative default ignore list for non-git roots
(tests, exported archives). Every record carries a SHA-256 of the file content,
which is the invalidation key for the whole content-addressed cache layer.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from postman_mcp.git.run import run_git

MAX_FILE_BYTES = 1_000_000  # symbol extraction on bigger files is never worth it

LANGUAGE_BY_EXT = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".rs": "rust",
    ".scala": "scala",
}

# Non-code files the corpus harvester wants to see.
CORPUS_EXTS = {".http", ".rest", ".json", ".yaml", ".yml"}

DEFAULT_IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", "site",
    "postman", "target", "vendor", ".next", ".nuxt", "coverage", ".tox",
}


@dataclass
class FileRecord:
    path: str        # repo-relative, posix separators
    language: str    # "" for non-code corpus files
    size: int
    sha256: str

    def to_doc(self) -> dict:
        return {"path": self.path, "language": self.language, "size": self.size, "sha256": self.sha256}

    @classmethod
    def from_doc(cls, d: dict) -> "FileRecord":
        return cls(path=d["path"], language=d["language"], size=d["size"], sha256=d["sha256"])


def scan_repo(root: Path) -> list[FileRecord]:
    """Inventory every code + corpus file under ``root``."""
    paths = _git_files(root)
    if paths is None:
        paths = _walk_files(root)
    records: list[FileRecord] = []
    for rel in sorted(paths):
        ext = Path(rel).suffix.lower()
        language = LANGUAGE_BY_EXT.get(ext, "")
        if not language and ext not in CORPUS_EXTS:
            continue
        full = root / rel
        try:
            data = full.read_bytes()
        except OSError:  # pragma: no cover - racing deletion
            continue
        if len(data) > MAX_FILE_BYTES:
            continue
        records.append(
            FileRecord(
                path=rel.replace("\\", "/"),
                language=language,
                size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return records


def _git_files(root: Path) -> list[str] | None:
    """``git ls-files`` including untracked-but-not-ignored; None if not a repo."""
    try:
        out = run_git(["ls-files", "--cached", "--others", "--exclude-standard"], root, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    files = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    # git lists deleted-but-tracked files too; keep only what exists.
    return [f for f in files if (root / f).is_file()]


def _walk_files(root: Path) -> list[str]:
    found: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:  # pragma: no cover - permission edge
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name not in DEFAULT_IGNORED_DIRS and not entry.name.startswith("."):
                    stack.append(entry)
            elif entry.is_file():
                found.append(str(entry.relative_to(root)))
    return found
