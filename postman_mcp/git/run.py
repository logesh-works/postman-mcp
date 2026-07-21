"""A ``git`` subprocess runner whose timeout is actually enforced on Windows.

``subprocess.run(..., capture_output=True, timeout=X)`` is not reliably bounded
by ``timeout`` on Windows. ``capture_output=True`` pipes stdout/stderr through
anonymous pipes, drained by internal reader threads
(``subprocess.Popen._communicate``); those pipes only signal EOF once *every*
handle to their write end is closed — not just the one child process this
``Popen`` spawned. If any other process on the system ends up holding a
duplicate of that handle (observed in practice: an IDE's own background
``git`` integration running concurrently against the same repo), the reader
threads — and therefore ``Popen.communicate()``'s internal ``join()`` — can
block forever. ``subprocess.run``'s ``timeout`` only bounds the *process*
wait; it does not save you from a stuck pipe read, so the call silently never
returns even though the child process itself may have already exited.

The fix: never create a shared, ownership-ambiguous pipe. Redirect stdout and
stderr to real files instead. A file has no "wait for every writer to close"
semantics — reading it after the child process itself has exited (confirmed
via ``Popen.wait(timeout=...)``, which waits on the process, never on a pipe)
is always safe and bounded.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class GitTimeout(subprocess.SubprocessError):
    """A git command exceeded its timeout and was killed.

    Subclasses ``subprocess.SubprocessError`` on purpose: every existing
    caller already catches that for other subprocess failures, so this slots
    in as one more reason a git call can fail, with no caller-side changes
    needed beyond swapping ``subprocess.run`` for :func:`run_git`.
    """


def _run_with_timeout(
    cmd: list[str], cwd: Path | str, *, timeout: float
) -> subprocess.CompletedProcess:
    """Run ``cmd`` with stdout/stderr captured via temp files, not pipes — see the
    module docstring for why that's the part that actually matters. Executable-agnostic
    so the timeout-enforcement behavior itself is directly testable without git.
    """
    with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=out_f, stderr=err_f)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()  # bounded: the process is already being torn down
            raise
        out_f.seek(0)
        err_f.seek(0)
        stdout = out_f.read().decode("utf-8", errors="replace")
        stderr = err_f.read().decode("utf-8", errors="replace")
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def run_git(
    args: list[str], cwd: Path | str, *, timeout: float = 30.0
) -> subprocess.CompletedProcess:
    """Run ``git <args>`` and return a ``CompletedProcess`` (stdout/stderr as text).

    Does not raise on a non-zero exit code — callers already check
    ``.returncode`` themselves, matching plain ``subprocess.run`` without
    ``check=True``. Raises ``FileNotFoundError`` if ``git`` isn't on PATH, or
    ``GitTimeout`` if it doesn't finish within ``timeout`` — the process is
    killed, not left running, before the exception propagates.
    """
    try:
        return _run_with_timeout(["git", *args], cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise GitTimeout(f"git {' '.join(args)} exceeded {timeout}s and was killed")
