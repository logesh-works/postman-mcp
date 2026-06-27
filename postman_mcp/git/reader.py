"""Resolve "what changed since X" by shelling to ``git``.

No ``gitpython`` dependency — shells straight out to the ``git`` binary instead. Powers
``syncchanges``: the zero-arg default diffs against ``lastUpdate.commit``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Raised when git is unavailable or a command fails."""


def _git(args: list[str], project_root: Path | str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    except subprocess.SubprocessError as exc:  # pragma: no cover - defensive
        raise GitError(str(exc)) from exc
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def current_commit(project_root: Path | str = ".") -> Optional[str]:
    """Short SHA of HEAD, or None if not a git repo / no commits."""
    try:
        return _git(["rev-parse", "--short", "HEAD"], project_root).strip() or None
    except GitError:
        return None


def resolve_since(ref: str) -> str:
    """Normalize a ``--since`` value (commit SHA or date) into a git revision."""
    return ref.strip()


def changed_files(
    project_root: Path | str = ".",
    *,
    last: Optional[int] = None,
    since: Optional[str] = None,
) -> list[str]:
    """Files changed for the given selector.

    - ``last=N``      → changes across the last N commits (no ``HEAD~N`` syntax for user).
    - ``since=<ref>`` → changes since a commit SHA or date.
    - neither        → changes in the working tree + last commit.
    """
    if last is not None:
        if last < 1:
            return []
        rng = f"HEAD~{last}..HEAD"
        out = _git(["diff", "--name-only", rng], project_root)
    elif since is not None:
        # Support both commit refs and dates (git accepts "--since" for dates via log).
        if _looks_like_date(since):
            out = _git(
                ["log", "--since", since, "--name-only", "--pretty=format:"],
                project_root,
            )
        else:
            out = _git(["diff", "--name-only", f"{since}..HEAD"], project_root)
    else:
        out = _git(["diff", "--name-only", "HEAD"], project_root)

    files = sorted({line.strip() for line in out.splitlines() if line.strip()})
    return files


def _looks_like_date(value: str) -> bool:
    return bool(value) and value[0].isdigit() and ("-" in value or "/" in value)
