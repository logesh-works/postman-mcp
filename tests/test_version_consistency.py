"""Version consistency — one authoritative source, everything else derives from it.

Guards against the exact drift QA found: ``pip show`` reporting a different version
than ``postman-mcp version`` because ``__version__`` was a second hardcoded literal.
"""

from __future__ import annotations

import re
from importlib.metadata import version
from pathlib import Path

from typer.testing import CliRunner

from postman_mcp import __version__
from postman_mcp.cli import app

runner = CliRunner()

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pyproject_version() -> str:
    text = _PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "pyproject.toml must declare a static [project].version"
    return match.group(1)


def test_package_version_matches_pyproject():
    assert __version__ == _pyproject_version()


def test_package_version_matches_installed_metadata():
    assert __version__ == version("postman-mcp")


def test_cli_version_matches_package_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
