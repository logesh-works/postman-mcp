"""The stdio MCP server — one tool per slash command.

Booted by ``postman-mcp serve`` (registered in Claude Code by ``init``). Reads
``postman/config.json`` from the launch CWD to know the target collection.

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
    """[Legacy — direct/scripted callers only] Sync ONE API by parsing code/OpenAPI
    yourself, with no LLM discovery step. target = function name | "METHOD /route" | code.

    The ``/postman:syncapi`` slash command does **not** call this tool — it calls
    ``get_sync_contract`` + ``sync_files`` instead (the LLM-driven V3 path), which is
    the recommended flow. This tool remains for MCP clients that want deterministic,
    LLM-free parsing (no citations, no hallucination-catching verification), and shares
    the same diff/merge engine (``postman/merge.py``) as ``sync_files`` so the two never
    disagree about what's new/modified/unchanged.

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
    """[Legacy — see :func:`syncapi`] Sync what changed since the last sync by parsing
    code/OpenAPI yourself. The ``/postman:syncchanges`` slash command uses
    ``get_sync_contract`` + ``sync_files`` instead. Diff first, write on confirm.

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
    """[Legacy — see :func:`syncapi`] Sync every API in one file / module / directory
    by parsing code/OpenAPI yourself. The ``/postman:sync`` slash command uses
    ``get_sync_contract`` + ``sync_files`` instead.

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
    """[Legacy — see :func:`syncapi`] Sync the whole codebase by parsing code/OpenAPI
    yourself. The ``/postman:syncall`` slash command uses ``get_sync_contract`` +
    ``sync_files`` instead. Diff first, write on confirm.

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
def index(refresh: bool = False) -> str:
    """Build/refresh the deterministic repository index (V3 Layer 0). Zero LLM cost.

    Returns the repo map: services, languages, symbol/import counts, files with
    decorated symbols (likely handlers/DTOs), and the evidence corpus summary.
    Call this once per session before ``context()``; pass ``refresh=True`` only
    if the cache seems stale (it invalidates per-file by content hash on its own).
    """
    from postman_mcp.service.repo import index_repo

    return index_repo(refresh=refresh)


@mcp.tool()
def context(target: str, budget: int = 8000) -> str:
    """Retrieve the focused context bundle for one endpoint/file (V3 retrieval).

    ``target`` = a handler/symbol name, ``"path/to/file.py"``,
    ``"file.py::symbol"``, or ``"METHOD /path"``. Returns symbol-aligned chunks
    (seed handler, DTO type closure, called services, router mount chain, test
    witnesses) headed with ``file:start-end`` anchors to cite, trimmed to
    ``budget`` estimated tokens. Use this instead of reading repository files
    directly — it is cheaper and the anchors are what verification will check.
    """
    from postman_mcp.service.repo import endpoint_context

    return endpoint_context(target, budget=budget)


@mcp.tool()
def compare_engines() -> str:
    """Diff V2 (parser) vs V3 (graph) route discovery over this repo (Phase 2 tooling).

    Read-only, no LLM involved. Useful while evaluating whether ``engine: "v3"`` is
    ready for this repo — reports which routes each side found and where they diverge.
    """
    from postman_mcp.service.compare import compare_engines as _compare

    return _compare(".")


@mcp.tool()
def validate_migration(min_recall: float = 1.0) -> str:
    """Migration-readiness gate: does the graph witness find every route the parser
    witness finds? Returns PASS/FAIL plus any routes the graph witness missed.

    Route recall only — the graph witness produces no request/response schema or
    auth detection, so a PASS is never license on its own to remove the parsers.
    """
    from postman_mcp.service.compare import validate_migration as _validate

    return _validate(".", min_recall=min_recall)


@mcp.tool()
def get_sync_contract(skills: Optional[list[str]] = None) -> dict:
    """Publish the LLM-driven sync contract — call once before writing ``postman/sync/``.

    Returns the cross-cutting workflow doc, a dict of individually loadable **skills**
    (single-responsibility discovery/building guides — a command names which subset it
    needs), the Postman Collection v2.1 schema URL ``collection.json`` must follow, and
    the JSON Schemas for ``metadata.json`` (per-endpoint citations + claimed DTO fields)
    and ``sync.config.json``. Any LLM can author valid artifacts from this alone; the MCP
    verifies the citations and syncs.

    Pass ``skills=["project-analysis", ...]`` to receive only the named skills (token
    optimization — your command's `.md` lists exactly which it needs); omit for all.
    ``available_skills`` always lists every name.
    """
    from postman_mcp.contract.publish import get_sync_contract as _get_sync_contract

    return _get_sync_contract(skills=skills, project_root=".")


@mcp.tool()
def cite(spans: list[dict]) -> str:
    """Compute verification-ready citations for file/line spans — use this instead of
    hashing by hand.

    Each span: ``{"file": "src/x.ts", "line_start": 10, "line_end": 14, "symbol": "Dto"?}``.
    Returns complete citation objects with ``snippet_sha256`` + ``quote`` filled in by the
    MCP (same hashing spec the verifier uses, so they always round-trip). Paste them
    directly into ``metadata.json``. Per-span errors for missing files/bad ranges; paths
    outside the project root are refused. Max 200 spans/call, 200 lines/span.
    """
    from postman_mcp.service.filesync import make_citations

    return make_citations(spans)


@mcp.tool()
def sync_files(
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    approve: Optional[list[str]] = None,
) -> str:
    """Validate, verify, diff, and (on confirm) sync the LLM-authored ``postman/sync/`` files.

    The LLM writes ``collection.json`` + ``metadata.json`` (+ ``sync.config.json``) first.
    This tool validates the collection shape, re-reads the cited source lines to verify
    the LLM didn't hallucinate (no source parsing — only cited-line re-reading), diffs
    against the live collection, and — with ``confirm=True`` — merges craft-preservingly
    and writes. ``confirm=False`` (default) previews only. Endpoints whose citation
    doesn't match the code are excluded unless named in ``approve=["METHOD:/path"]``.
    """
    from postman_mcp.service.filesync import sync_from_files

    return sync_from_files(
        into=into, confirm=confirm, confirm_collection=confirm_collection, approve=approve,
    )


@mcp.tool()
def sync_env(confirm: bool = False) -> str:
    """Create a Postman environment from the LLM-authored ``postman/sync/environment.json``.

    The LLM discovers env vars / base URLs / secrets from the code and writes
    ``environment.json`` (``{name, values:[{key,value,type,enabled}]}``); this tool
    previews (``confirm=False``) then creates it in the configured workspace
    (``confirm=True``). Mark secret-like variables with ``type: "secret"``.
    """
    from postman_mcp.service.filesync import sync_env_from_file

    return sync_env_from_file(confirm=confirm)


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
    """[Legacy — see :func:`syncapi`] Generate a Postman environment from code, inferring
    variables yourself instead of via the LLM-authored ``environment.json`` the
    ``/postman:createenv`` slash command uses (that command calls ``sync_env`` instead).
    Idempotent like ``sync_env``: re-running with the same name updates the environment
    this project already created rather than making a duplicate.
    """
    from postman_mcp.service.environment import create_env

    return create_env(name=name, confirm=confirm)


@mcp.tool()
def status(since: Optional[str] = None) -> str:
    """[Legacy — see :func:`syncapi`] Read-only drift check computed by parsing
    code/OpenAPI yourself — what WOULD sync, no writes. The ``/postman:status`` slash
    command uses ``get_sync_contract`` + ``sync_files(confirm=false)`` instead.
    """
    from postman_mcp.service.status import status_report

    return status_report(since=since)


def run() -> None:  # pragma: no cover - process entry
    """Run the stdio server (called by ``postman-mcp serve``)."""
    mcp.run()
