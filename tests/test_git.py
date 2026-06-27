"""Git reader — 'what changed since X' (PRD §5, §10.1)."""

from __future__ import annotations

import subprocess

import pytest

from postman_mcp.git.reader import (
    _looks_like_date,
    changed_files,
    current_commit,
    resolve_since,
)


def _run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def git_repo(tmp_path):
    try:
        _run(["git", "init"], tmp_path)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    _run(["git", "config", "user.email", "t@example.com"], tmp_path)
    _run(["git", "config", "user.name", "Test"], tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    _run(["git", "add", "."], tmp_path)
    _run(["git", "commit", "-m", "init"], tmp_path)
    return tmp_path


def test_current_commit_none_outside_repo(tmp_path):
    assert current_commit(tmp_path) is None


def test_current_commit_in_repo(git_repo):
    sha = current_commit(git_repo)
    assert sha and len(sha) >= 4


def test_changed_files_in_working_tree(git_repo):
    (git_repo / "routes.py").write_text("y = 2\n", encoding="utf-8")
    _run(["git", "add", "."], git_repo)
    files = changed_files(git_repo)
    assert "routes.py" in files


def test_changed_files_last_zero_is_empty(git_repo):
    assert changed_files(git_repo, last=0) == []


def test_resolve_since_passthrough():
    assert resolve_since("  a1b2c3d  ") == "a1b2c3d"


@pytest.mark.parametrize("value,expected", [
    ("2026-06-01", True),
    ("2026/06/01", True),
    ("a1b2c3d", False),
    ("", False),
])
def test_looks_like_date(value, expected):
    assert _looks_like_date(value) is expected
