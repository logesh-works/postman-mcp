"""The Evidence Auditor — the anti-hallucination core.

For every citation: confine it to the repo, re-read the exact lines, re-hash them
identically to the playbook's spec, and check the symbol actually occurs in the span.
A mismatch is further classified as *fabricated* (the citation was never true, even at
the model's declared commit) or *stale* (true at that commit, but the file has since
changed).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Literal, Optional

from postman_mcp.contract.schema import Evidence
from postman_mcp.git.run import run_git

EvidenceVerdict = Literal["verified", "fabricated", "stale", "unreadable", "confinement_violation"]

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def normalize_snippet(lines: list[str]) -> str:
    """LF-normalized, trailing-whitespace-stripped join — the shared hashing spec."""
    return "\n".join(line.rstrip() for line in lines)


def hash_snippet(lines: list[str]) -> str:
    return hashlib.sha256(normalize_snippet(lines).encode("utf-8")).hexdigest()


def is_confined(project_root: Path, rel_file: str) -> bool:
    """Reject path traversal / absolute paths — V-10's confinement half.

    Absolute-path detection can't rely on ``Path.is_absolute()`` alone: it's
    platform-native, so a Windows drive-letter path like ``C:/Windows/system.ini``
    is *not* absolute according to POSIX ``pathlib`` and would otherwise slip
    through on Linux/macOS as a harmless-looking relative path. A citation should
    be rejected the same way regardless of which OS the MCP server runs on.
    """
    if not rel_file or rel_file.startswith(("/", "\\")) or _WINDOWS_DRIVE_RE.match(rel_file):
        return False
    candidate = Path(rel_file)
    if candidate.is_absolute():
        return False
    if ".." in candidate.parts:
        return False
    try:
        resolved = (project_root / candidate).resolve()
        resolved.relative_to(project_root.resolve())
    except (ValueError, OSError):
        return False
    return True


def _read_lines(path: Path) -> Optional[list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return text.splitlines()


def _git_show(project_root: Path, commit: str, rel_file: str) -> Optional[str]:
    """``git show {commit}:{file}`` — ``None`` if the commit or file isn't available."""
    try:
        proc = run_git(["show", f"{commit}:{rel_file}"], project_root, timeout=15)
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def audit_evidence(
    evidence: Evidence,
    project_root: Path | str,
    *,
    repo_commit: Optional[str] = None,
) -> tuple[EvidenceVerdict, dict]:
    """Re-verify one citation. Returns ``(verdict, detail)`` for the finding message."""
    root = Path(project_root).resolve()

    if not is_confined(root, evidence.file):
        return "confinement_violation", {"file": evidence.file}

    abs_path = root / evidence.file
    if not abs_path.is_file():
        return "unreadable", {"file": evidence.file, "reason": "file does not exist"}

    lines = _read_lines(abs_path)
    if lines is None:
        return "unreadable", {"file": evidence.file, "reason": "could not decode file"}

    if evidence.line_start < 1 or evidence.line_end < evidence.line_start:
        return "unreadable", {"file": evidence.file, "reason": "invalid line range"}
    if evidence.line_end > len(lines):
        # Working tree is shorter than cited — could be current mismatch (stale/fabricated)
        # or a genuinely invalid citation; treated as a hash mismatch below via a probe read.
        cited = lines[evidence.line_start - 1:] if evidence.line_start <= len(lines) else []
    else:
        cited = lines[evidence.line_start - 1 : evidence.line_end]

    working_hash = hash_snippet(cited) if cited else ""
    if working_hash == evidence.snippet_sha256 and cited:
        if evidence.symbol and not any(evidence.symbol in line for line in cited):
            return "unreadable", {
                "file": evidence.file,
                "reason": f"symbol {evidence.symbol!r} not found in cited span",
            }
        return "verified", {}

    detail = {
        "file": evidence.file,
        "expected": evidence.snippet_sha256,
        "actual": working_hash,
    }

    # Distinguish fabricated (never true) from stale (true at the declared commit).
    if repo_commit:
        historical = _git_show(root, repo_commit, evidence.file)
        if historical is not None:
            hist_lines = historical.splitlines()
            if evidence.line_end <= len(hist_lines) and evidence.line_start >= 1:
                hist_cited = hist_lines[evidence.line_start - 1 : evidence.line_end]
                hist_hash = hash_snippet(hist_cited)
                if hist_hash == evidence.snippet_sha256:
                    return "stale", detail
            return "fabricated", detail
        # Commit unavailable (shallow clone) → conservative: treat as stale, not fabricated.
        return "stale", detail

    # No declared commit to check against — conservative default is stale, not fabricated,
    # since we cannot prove the citation was never true.
    return "stale", detail
