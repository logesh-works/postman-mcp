"""Regression tests for the Windows pipe-deadlock fix in git/run.py.

The bug this guards against: subprocess.run(..., capture_output=True,
timeout=X) is not reliably bounded by `timeout` on Windows, because
capture_output pipes stdout/stderr through anonymous pipes whose EOF depends
on every handle to the write end being closed — not just the process this
Popen spawned. Observed in production: a `git rev-parse` call inside
sync_files blocked for 9+ minutes (CPU flat at ~0, so genuinely stuck, not
slow) while an unrelated IDE git process ran concurrently against the same
repo. run_git() sidesteps the whole hazard by capturing through real files
instead of pipes.

These tests use `sys.executable` as a portable stand-in for a slow/hanging
subprocess, so timeout enforcement is verified deterministically without
depending on git's own timing or on reproducing the exact cross-process
handle-sharing race (which is inherently non-deterministic).
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from postman_mcp.git.run import GitTimeout, _run_with_timeout, run_git


def test_run_with_timeout_captures_stdout_stderr_and_returncode(tmp_path: Path):
    result = _run_with_timeout(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"],
        tmp_path,
        timeout=10,
    )
    assert result.returncode == 3
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"


def test_run_with_timeout_handles_large_output(tmp_path: Path):
    """Historically, PIPE-based capture without careful concurrent draining could
    also deadlock on large output filling the OS pipe buffer. Temp files have no
    such limit — this is a basic sanity check that the swap didn't trade one
    deadlock for another."""
    result = _run_with_timeout(
        [sys.executable, "-c", "print('x' * 500_000)"],
        tmp_path,
        timeout=10,
    )
    assert result.returncode == 0
    assert len(result.stdout.strip()) == 500_000


def test_run_with_timeout_actually_enforces_the_timeout(tmp_path: Path):
    """The core regression guard: a process that outlives `timeout` must cause
    a bounded, prompt TimeoutExpired — not an indefinite hang. Elapsed wall time
    is asserted well under the process's own 10s sleep, proving we didn't just
    wait for it to finish anyway."""
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        _run_with_timeout(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            tmp_path,
            timeout=1,
        )
    elapsed = time.monotonic() - start
    assert elapsed < 5  # generous slack; must be nowhere near the 10s sleep


def test_run_with_timeout_kills_the_process_on_timeout(tmp_path: Path):
    """Not just raising promptly — the child must actually be terminated, not
    left running in the background after we've given up waiting on it."""
    marker = tmp_path / "still_running.txt"
    with pytest.raises(subprocess.TimeoutExpired):
        _run_with_timeout(
            [
                sys.executable, "-c",
                f"import time; time.sleep(2); open(r'{marker}', 'w').close()",
            ],
            tmp_path,
            timeout=0.2,
        )
    time.sleep(2.5)  # past when the marker would appear if the process survived
    assert not marker.exists()


def test_run_git_wraps_timeout_as_git_timeout(tmp_path: Path, monkeypatch):
    import postman_mcp.git.run as run_mod

    def fake_timeout(cmd, cwd, *, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(run_mod, "_run_with_timeout", fake_timeout)
    with pytest.raises(GitTimeout):
        run_git(["status"], tmp_path, timeout=1)


def test_run_git_basic_success_against_this_repo():
    result = run_git(["rev-parse", "--is-inside-work-tree"], Path(__file__).parent.parent)
    assert result.returncode == 0
    assert result.stdout.strip() == "true"
