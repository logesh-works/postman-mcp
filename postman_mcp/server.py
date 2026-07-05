"""The stdio MCP server — one tool per slash command.

Booted by ``postman-mcp serve`` (registered in Claude Code by ``init``). Reads
``postman-mcp.json`` from the launch CWD to know the target collection.

These handlers are thin adapters: they parse MCP args and call the service layer, which
holds all business logic and enforces the safety rules. Every write-capable
tool follows the two-phase ``confirm`` contract — with ``confirm=False`` (default) it
returns the diff preview and writes nothing; only ``confirm=True`` performs the write
.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("postman-mcp")


@mcp.tool()
def syncapi(
    target: str,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    overrides: Optional[dict[str, Any]] = None,
) -> str:
    """Sync ONE API (the kernel). target = function name | "METHOD /route" | code.

    With confirm=False returns the diff preview; with confirm=True writes.
    ``overrides`` is an optional patch — shaped like the Postman item (or a subset,
    e.g. ``{"response": [...]}``) — merged onto the deterministically built item
    before diffing/writing. It carries free-form ``/postman:prompt`` instructions
    (extra error responses, extra headers, an edited description, ...) into the
    sync; everything still goes through the diff preview before any write.
    """
    from postman_mcp.service.sync import sync_api

    return sync_api(
        target,
        into=into,
        confirm=confirm,
        confirm_collection=confirm_collection,
        overrides=overrides,
    )


@mcp.tool()
def syncchanges(
    last: Optional[int] = None,
    since: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    overrides: Optional[dict[str, Any]] = None,
) -> str:
    """Sync what changed since the last sync. Diff first, write on confirm.

    ``overrides`` — see :func:`syncapi` — is applied identically to every route in
    this sync.
    """
    from postman_mcp.service.sync import sync_changes

    return sync_changes(
        last=last,
        since=since,
        confirm=confirm,
        confirm_collection=confirm_collection,
        overrides=overrides,
    )


@mcp.tool()
def sync(
    target: str,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    overrides: Optional[dict[str, Any]] = None,
) -> str:
    """Sync every API in one file / module / directory.

    ``overrides`` — see :func:`syncapi` — is applied identically to every route in
    this sync.
    """
    from postman_mcp.service.sync import sync_target

    return sync_target(
        target,
        into=into,
        confirm=confirm,
        confirm_collection=confirm_collection,
        overrides=overrides,
    )


@mcp.tool()
def syncall(
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    overrides: Optional[dict[str, Any]] = None,
) -> str:
    """Sync the whole codebase. Diff first, write on confirm.

    ``overrides`` — see :func:`syncapi` — is applied identically to every route in
    this sync.
    """
    from postman_mcp.service.sync import sync_all

    return sync_all(
        into=into,
        confirm=confirm,
        confirm_collection=confirm_collection,
        overrides=overrides,
    )


@mcp.tool()
def get_contract(version: str = "1") -> dict:
    """Publish the APIM schema + discovery playbook — call once before any repo analysis.

    Any LLM (Claude, GPT, Gemini, ...) can produce a valid Canonical API Model (APIM)
    from this response alone: the JSON Schema it must conform to, the framework-agnostic
    discovery playbook, per-framework guides, and the confidence-class reference.
    """
    from postman_mcp.service.aiplan import get_contract_tool

    return get_contract_tool(version)


@mcp.tool()
def submit_model(
    model_path: Optional[str] = None,
    model_json: Optional[dict[str, Any]] = None,
) -> str:
    """Submit an APIM document for verification. Returns the model_id + VerificationReport.

    Every fact must carry evidence (file/line/symbol/hash) — the pipeline re-reads and
    re-hashes every citation, cross-checks against the independent parser-based "witness"
    engine, and rejects endpoints that fail (hallucination, duplicate identity, invalid
    schema, unresolved refs, ...). Fix any rejected/warned endpoints named in the report
    and resubmit; resubmission is idempotent.
    """
    from postman_mcp.service.aiplan import submit_model as _submit

    return _submit(model_path=model_path, model_json=model_json)


@mcp.tool()
def verify_model(model_id: str) -> str:
    """Re-run verification for a previously submitted model (freshness re-check)."""
    from postman_mcp.service.aiplan import verify_model as _verify

    return _verify(model_id)


@mcp.tool()
def plan(
    model_id: Optional[str] = None,
    uids: Optional[list[str]] = None,
    file: Optional[str] = None,
    into: Optional[str] = None,
    dry_run: bool = False,
    overrides: Optional[dict[str, Any]] = None,
) -> str:
    """Compile a diff for a scope of verified endpoints. Returns the preview + plan_id.

    ``model_id`` — a previously submitted/verified model; omit to use the witness
    engine's own model (parser-first fallback, keeps working with no LLM analysis at
    all). ``uids``/``file`` narrow the scope; omit both to plan every syncable endpoint.
    ``dry_run=True`` renders the preview without persisting a plan (guaranteed no-write
    path). Endpoints below the auto-sync confidence threshold are listed separately and
    require an explicit ``apply(..., approve=[uid])``.
    """
    from postman_mcp.service.aiplan import plan as _plan

    return _plan(model_id=model_id, uids=uids, file=file, into=into, dry_run=dry_run, overrides=overrides)


@mcp.tool()
def apply(
    plan_id: str,
    approve: Optional[list[str]] = None,
    confirm: bool = True,
) -> str:
    """Execute a plan produced by ``plan()``. The only tool that writes to Postman.

    Aborts (no partial write) if the live collection changed since the plan was
    compiled, if the plan expired, or if ``approve`` names a uid outside the plan's
    needs-approval set. Snapshots the collection before writing, so every apply is
    reversible via ``rollback``.
    """
    from postman_mcp.service.aiplan import apply as _apply

    return _apply(plan_id, approve=approve, confirm=confirm)


@mcp.tool()
def snapshot(label: Optional[str] = None) -> str:
    """Snapshot the live collection now, independent of any sync."""
    from postman_mcp.service.aiplan import snapshot as _snapshot

    return _snapshot(label=label)


@mcp.tool()
def rollback(snapshot_id: str, confirm: bool = False) -> str:
    """Preview (confirm=False) or perform (confirm=True) restoring a prior snapshot.

    The current state is itself snapshotted first, so a rollback is always reversible.
    """
    from postman_mcp.service.aiplan import rollback as _rollback

    return _rollback(snapshot_id, confirm=confirm)


@mcp.tool()
def audit(last: int = 20) -> str:
    """Show recent audit-log entries (submit/plan/apply/rollback), newest last."""
    from postman_mcp.service.aiplan import audit_log

    return audit_log(last=last)


@mcp.tool()
def createenv(name: Optional[str] = None, confirm: bool = False) -> str:
    """Generate a Postman environment from code."""
    from postman_mcp.service.environment import create_env

    return create_env(name=name, confirm=confirm)


@mcp.tool()
def status(since: Optional[str] = None) -> str:
    """Read-only drift check — what WOULD sync, no writes."""
    from postman_mcp.service.status import status_report

    return status_report(since=since)


def run() -> None:  # pragma: no cover - process entry
    """Run the stdio server (called by ``postman-mcp serve``)."""
    mcp.run()
