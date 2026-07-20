"""The submitted-model tool surface — get_contract / submit_model / verify_model /
plan / apply / snapshot / rollback / audit.

Every write still funnels through the same two-phase discipline the legacy commands
use (``service/sync.py``), extended with a persisted plan token so ``apply`` writes
exactly what ``plan`` previewed — or aborts if the collection or the model has moved
since.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Optional

from postman_mcp.config.store import ConfidencePolicyConfig, ConfigError
from postman_mcp.confidence.policy import PolicyConfig
from postman_mcp.contract.publish import get_contract
from postman_mcp.contract.schema import ApiModel
from postman_mcp.git.reader import current_commit
from postman_mcp.model.store import ModelIngestError, load_model, load_model_from_path, save_model, save_report
from postman_mcp.models import RouteModel
from postman_mcp.plan.compiler import (
    PLANS_DIRNAME,
    PlanDocument,
    compile_plan,
    load_plan,
    plan_is_expired,
)
from postman_mcp.plan.render import render_plan_preview
from postman_mcp.postman import merge
from postman_mcp.postman.client import PostmanAuthError, PostmanError
from postman_mcp.safety.audit import append_event, read_events
from postman_mcp.safety.rollback import diff_rollback, render_rollback_preview
from postman_mcp.safety.snapshots import load_snapshot, save_snapshot
from postman_mcp.service.context import load_context
from postman_mcp.service.sync import _resolve_into, _record_sync
from postman_mcp.verify.graph_witness import build_graph_witness
from postman_mcp.verify.pipeline import run_pipeline
from postman_mcp.verify.render import render_report
from postman_mcp.witness.engine import build_witness_set, witness_to_apim


def get_contract_tool(version: str = "1") -> dict:
    return get_contract(version)


def _policy_from_config(cfg) -> PolicyConfig:
    cp: ConfidencePolicyConfig = cfg.confidencePolicy
    return PolicyConfig(
        auto_threshold=cp.autoThreshold,
        flag_threshold=cp.flagThreshold,
        approval_threshold=cp.approvalThreshold,
        allow_low_confidence=cfg.allowLowConfidence,
    )


def submit_model(
    model_path: Optional[str] = None,
    model_json: Optional[dict] = None,
    *,
    project_root: Path | str = ".",
) -> str:
    """Ingest, verify, and report on an LLM-produced APIM document."""
    if model_path is None and model_json is None:
        return "Error: provide either model_path or model_json."
    try:
        raw: Any = Path(model_path).read_text(encoding="utf-8") if model_path else model_json
        model_id, model = save_model(raw, project_root)
    except (ModelIngestError, OSError) as exc:
        return f"Model rejected (BLOCK_MODEL): {exc}"

    report = run_pipeline(model, project_root, repo_commit=model.repo.commit or current_commit(project_root))
    save_report(model_id, report.model_dump_json(), project_root)
    append_event(
        project_root, "submit", actor=model.generator.provider, model_id=model_id,
        outcome="ok" if report.verdict != "blocked" else "blocked",
        detail={"verdict": report.verdict},
    )
    return render_report(report)


def verify_model(model_id: str, *, project_root: Path | str = ".") -> str:
    """Re-run verification against the current working tree (freshness re-check)."""
    try:
        model = load_model(model_id, project_root)
    except ModelIngestError as exc:
        return f"Error: {exc}"
    report = run_pipeline(model, project_root, repo_commit=model.repo.commit or current_commit(project_root))
    save_report(model_id, report.model_dump_json(), project_root)
    return render_report(report)


def _witness_fallback_model(project_root: Path | str, cfg) -> tuple[str, ApiModel]:
    """No submitted model → keep everything working with zero LLM analysis.

    ``engine: "v2"`` (default for pre-V3 projects) uses the parser witness — full
    fidelity (schema, auth). ``engine: "v3"`` (default for new `init`s) uses the
    graph witness instead — route identity only, no schema/auth extraction (see
    ``docs/architecture/v3-proposal.md``'s Phase 5 evaluation for why the parsers
    aren't removed). This fallback is a safety net for when nothing has been
    submitted at all; the intended V3 workflow is the AI-submitted model via
    `get_contract`/`index`/`context`/`submit_model`, which never reaches this path.
    """
    if getattr(cfg, "engine", "v2") == "v3":
        witness = build_graph_witness(project_root)
    else:
        witness = build_witness_set(project_root, cfg)
    apim = witness_to_apim(witness, project_root=project_root, repo_commit=current_commit(project_root))
    return save_model(apim, project_root)


def plan(
    *,
    model_id: Optional[str] = None,
    uids: Optional[list[str]] = None,
    file: Optional[str] = None,
    into: Optional[str] = None,
    dry_run: bool = False,
    overrides: Optional[dict] = None,
    project_root: Path | str = ".",
) -> str:
    """Diff a scope of endpoints against the live collection."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    if model_id is None:
        model_id, model = _witness_fallback_model(ctx.project_root, ctx.config.config)
        report = run_pipeline(model, ctx.project_root, repo_commit=model.repo.commit)
    else:
        try:
            model = load_model(model_id, ctx.project_root)
        except ModelIngestError as exc:
            ctx.client.close()
            return f"Error: {exc}"
        report = run_pipeline(model, ctx.project_root, repo_commit=model.repo.commit or current_commit(ctx.project_root))

    scope_uids: Optional[set[str]] = None
    if uids:
        scope_uids = set(uids)
    elif file:
        needle = file.strip().lstrip("-").lower()
        scope_uids = {
            ep.uid for ep in model.endpoints
            if ep.identity_evidence and needle in ep.identity_evidence[0].file.lower()
        }
        if not scope_uids:
            ctx.client.close()
            return f"No endpoints found matching file {file!r}."

    into_path = _resolve_into(into, ctx.config.config)
    policy = _policy_from_config(ctx.config.config)
    doc = compile_plan(
        model, report, collection=ctx.collection, collection_id=ctx.collection_id,
        scope_uids=scope_uids, into=into_path, generate_tests=ctx.config.config.generateTests,
        response_style=ctx.config.config.responseStyle, overrides=overrides, policy=policy,
        project_root=ctx.project_root,
    )
    ctx.client.close()

    append_event(
        ctx.project_root, "plan", model_id=report.model_id, plan_id=doc.plan_id,
        collection_id=ctx.collection_id,
        endpoints={"auto_flag": len(doc.auto_and_flag_uids()), "needs_approval": len(doc.needs_approval_uids()),
                   "rejected": len(doc.rejected), "blocked": len(doc.blocked_uids)},
        outcome="dry_run" if dry_run else "ok",
    )

    preview = render_plan_preview(doc, collection_name=ctx.collection_name)
    if dry_run:
        (Path(ctx.project_root) / PLANS_DIRNAME / f"{doc.plan_id}.json").unlink(missing_ok=True)
        preview = preview.replace(doc.plan_id, f"{doc.plan_id} (dry run — not persisted)")
    return report.summary + "\n\n" + preview


def apply(
    plan_id: str,
    *,
    approve: Optional[list[str]] = None,
    confirm: bool = True,
    project_root: Path | str = ".",
) -> str:
    """Execute a previously compiled plan — the only path that writes to Postman."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    write_protection = ctx.config.config.writeProtection
    if write_protection == "readonly":
        ctx.client.close()
        return "Write refused: writeProtection is set to 'readonly'."

    try:
        doc: PlanDocument = load_plan(plan_id, ctx.project_root)
    except FileNotFoundError as exc:
        ctx.client.close()
        return f"Error: {exc}"

    if plan_is_expired(doc, ttl_hours=ctx.config.config.planTtlHours):
        ctx.client.close()
        return "Plan expired — re-run plan(...) to refresh the preview."

    from postman_mcp.plan.compiler import collection_hash

    if collection_hash(ctx.collection) != doc.collection_hash:
        ctx.client.close()
        return "Collection changed since preview — re-plan (apply refuses to write a stale plan)."

    approve_set = set(approve or [])
    unknown = approve_set - set(doc.needs_approval_uids())
    if unknown:
        ctx.client.close()
        return f"Error: approve() names uid(s) not in this plan's needs-approval set: {sorted(unknown)}"

    if write_protection == "approve-all":
        entries = [e for e in doc.entries if e.uid in approve_set]
    else:
        entries = [e for e in doc.entries if e.gate_action in ("auto", "flag") or e.uid in approve_set]

    if not confirm:
        ctx.client.close()
        return f"Nothing written (confirm=False). {len(entries)} entrie(s) would apply."

    if not entries:
        ctx.client.close()
        return "Nothing to write — no entries selected (check approve() for needs-approval endpoints)."

    try:
        snapshot_id = save_snapshot(ctx.collection, ctx.collection_id, ctx.project_root, label="pre-apply")
    except OSError as exc:
        ctx.client.close()
        append_event(ctx.project_root, "apply", plan_id=plan_id, outcome="error",
                     detail={"reason": f"snapshot failed: {exc}"})
        return f"Write refused: could not write a pre-write snapshot ({exc})."

    working = copy.deepcopy(ctx.collection)
    new = mod = 0
    for entry in entries:
        route = RouteModel.model_validate(entry.route)
        change = merge.apply_route(working, entry.item, route, entry.into)
        if change.value == "new":
            new += 1
        elif change.value == "modified":
            mod += 1
        # "unchanged": apply_route left this entry untouched — not counted as a write,
        # so the completion summary doesn't overstate what changed.

    try:
        ctx.client.update_collection(ctx.collection_id, working)
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        append_event(ctx.project_root, "apply", plan_id=plan_id, snapshot_id=snapshot_id,
                     collection_id=ctx.collection_id, outcome="error", detail={"reason": str(exc)})
        return f"Write aborted (no partial write): {exc}"

    _record_sync(ctx)
    ctx.client.close()
    append_event(
        ctx.project_root, "apply", model_id=doc.model_id, plan_id=plan_id, snapshot_id=snapshot_id,
        collection_id=ctx.collection_id, endpoints={"new": new, "modified": mod}, outcome="ok",
    )
    lines = []
    if new:
        lines.append(f"✓ {new} API(s) added")
    if mod:
        lines.append(f"✓ {mod} API(s) updated")
    lines.append(f"✓ Snapshot recorded ({snapshot_id})")
    lines.append("✓ Collection updated")
    lines.append("✓ Apply completed")
    return "\n".join(lines)


def snapshot(label: Optional[str] = None, *, project_root: Path | str = ".") -> str:
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"
    snap_id = save_snapshot(ctx.collection, ctx.collection_id, ctx.project_root, label=label)
    ctx.client.close()
    append_event(ctx.project_root, "snapshot", snapshot_id=snap_id, collection_id=ctx.collection_id)
    return f"✓ Snapshot recorded: {snap_id}"


def rollback(snapshot_id: str, *, confirm: bool = False, project_root: Path | str = ".") -> str:
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"
    try:
        snap = load_snapshot(snapshot_id, ctx.project_root)
    except FileNotFoundError as exc:
        ctx.client.close()
        return f"Error: {exc}"

    diff = diff_rollback(ctx.collection, snap["collection"])
    if not confirm:
        ctx.client.close()
        return render_rollback_preview(snapshot_id, diff)

    pre_rollback_id = save_snapshot(ctx.collection, ctx.collection_id, ctx.project_root, label="pre-rollback")
    try:
        ctx.client.update_collection(ctx.collection_id, snap["collection"])
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        append_event(ctx.project_root, "rollback", snapshot_id=snapshot_id, outcome="error", detail={"reason": str(exc)})
        return f"Rollback aborted (no partial write): {exc}"
    ctx.client.close()
    append_event(ctx.project_root, "rollback", snapshot_id=snapshot_id, collection_id=ctx.collection_id,
                 outcome="ok", detail={"pre_rollback_snapshot": pre_rollback_id})
    return f"✓ Restored to {snapshot_id}; prior state saved as {pre_rollback_id}."


def audit_log(last: int = 20, *, project_root: Path | str = ".") -> str:
    events = read_events(project_root, last=last)
    if not events:
        return "No audit events recorded yet."
    lines = []
    for e in events:
        lines.append(f"{e['ts']}  {e['event']:<10} outcome={e['outcome']}  " + " ".join(
            f"{k}={v}" for k, v in e.items() if k not in ("ts", "event", "outcome", "detail") and v
        ))
    return "\n".join(lines)
