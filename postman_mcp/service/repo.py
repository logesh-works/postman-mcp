"""Service layer for the V3 repository-understanding tools (``index``/``context``).

Deliberately independent of ``postman/config.json`` and the Postman client:
indexing and retrieval are read-only repository operations and must work
before ``init``, on any checkout, with no credentials. Errors come back as
readable tool output, never tracebacks.
"""

from __future__ import annotations

from postman_mcp.retrieve import SliceError, assemble_context, index_summary


def index_repo(refresh: bool = False) -> str:
    try:
        return index_summary(".", refresh=refresh)
    except Exception as exc:  # noqa: BLE001 - tool boundary
        return f"Index failed: {exc}"


def endpoint_context(target: str, budget: int = 8000) -> str:
    if not target or not target.strip():
        return "context() needs a target: a symbol name, 'path/to/file', 'file::symbol', or 'METHOD /path'."
    try:
        return assemble_context(".", target, budget=budget)
    except SliceError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 - tool boundary
        return f"Context assembly failed: {exc}"
