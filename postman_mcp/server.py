"""The stdio MCP server — one tool per slash command (PRD §5, §10).

Booted by ``postman-mcp serve`` (registered in Claude Code by ``init``). Reads
``postman-mcp.json`` from the launch CWD to know the target collection (PRD §C.2a).

These handlers are thin adapters: they parse MCP args and call the service layer, which
holds all business logic and enforces the safety rules (PRD §17). Every write-capable
tool follows the two-phase ``confirm`` contract — with ``confirm=False`` (default) it
returns the diff preview and writes nothing; only ``confirm=True`` performs the write
(PRD §13, §17).
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("postman-mcp")


@mcp.tool()
def syncapi(
    target: str,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
) -> str:
    """Sync ONE API (the kernel). target = function name | "METHOD /route" | code.

    With confirm=False returns the diff preview; with confirm=True writes (PRD §10.1).
    """
    from postman_mcp.service.sync import sync_api

    return sync_api(
        target, into=into, confirm=confirm, confirm_collection=confirm_collection
    )


@mcp.tool()
def syncchanges(
    last: Optional[int] = None,
    since: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
) -> str:
    """Sync what changed since the last sync (PRD §10.1). Diff first, write on confirm."""
    from postman_mcp.service.sync import sync_changes

    return sync_changes(
        last=last, since=since, confirm=confirm, confirm_collection=confirm_collection
    )


@mcp.tool()
def sync(
    target: str,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
) -> str:
    """Sync every API in one file / module / directory (PRD §10.1)."""
    from postman_mcp.service.sync import sync_target

    return sync_target(
        target, into=into, confirm=confirm, confirm_collection=confirm_collection
    )


@mcp.tool()
def syncall(
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
) -> str:
    """Sync the whole codebase (PRD §10.1). Diff first, write on confirm."""
    from postman_mcp.service.sync import sync_all

    return sync_all(into=into, confirm=confirm, confirm_collection=confirm_collection)


@mcp.tool()
def createenv(name: Optional[str] = None, confirm: bool = False) -> str:
    """Generate a Postman environment from code (PRD §10.1, §16)."""
    from postman_mcp.service.environment import create_env

    return create_env(name=name, confirm=confirm)


@mcp.tool()
def status(since: Optional[str] = None) -> str:
    """Read-only drift check — what WOULD sync, no writes (PRD §10.2)."""
    from postman_mcp.service.status import status_report

    return status_report(since=since)


def run() -> None:  # pragma: no cover - process entry
    """Run the stdio server (called by ``postman-mcp serve``)."""
    mcp.run()
