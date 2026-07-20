"""Postman MCP — sync API code into Postman collections from Claude Code.

Public entry points:
- ``postman_mcp.cli:main`` — the ``postman-mcp`` terminal command.
- ``postman_mcp.server`` — the stdio MCP server booted by ``postman-mcp serve``.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    # ``pyproject.toml``'s ``[project].version`` is the single source of truth — read
    # from the installed distribution's own metadata so this can never drift from it
    # (previously a second hardcoded literal here could silently disagree with
    # ``pip show`` / build output after a version bump touched one but not the other).
    __version__ = version("postman-mcp")
except PackageNotFoundError:  # pragma: no cover - only when genuinely not installed
    __version__ = "0.0.0-dev"
