"""The Plan Compiler — verified APIM endpoints → an executable, hash-bound plan.

Compiles each syncable endpoint through the *unchanged* engine (``build_request_item``)
and merge layer (``merge.compute_diff``), partitions endpoints by their confidence gate
action, and persists everything the Executor needs so ``apply(plan_id)`` writes exactly
what was previewed — never a re-derived version of it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from postman_mcp.confidence.policy import PolicyConfig, gate_action
from postman_mcp.confidence.scorer import gate_score
from postman_mcp.contract.schema import ApiModel, Endpoint
from postman_mcp.engine.builder import build_request_item
from postman_mcp.model.adapter import endpoint_to_route_model
from postman_mcp.models import RequestDiff, RouteModel
from postman_mcp.postman import merge
from postman_mcp.verify.report import VerificationReport

PLANS_DIRNAME = ".postman-mcp/plans"
ENGINE_VERSION = "1"
DEFAULT_PLAN_TTL_HOURS = 24

GateAction = Literal["auto", "flag", "needs_approval", "blocked"]


class PlanEntry(BaseModel):
    uid: str
    gate_action: GateAction
    confidence: dict[str, int] = Field(default_factory=dict)
    route: dict[str, Any]     # RouteModel.model_dump()
    item: dict[str, Any]      # the built Postman item — frozen at plan time
    diff: dict[str, Any]      # RequestDiff.model_dump() — frozen at plan time
    into: str


class PlanDocument(BaseModel):
    plan_id: str
    model_id: str
    collection_id: str
    collection_hash: str
    engine_version: str = ENGINE_VERSION
    created_at: str
    into_default: str = "/"
    entries: list[PlanEntry] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
    blocked_uids: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)

    def entry(self, uid: str) -> Optional[PlanEntry]:
        for e in self.entries:
            if e.uid == uid:
                return e
        return None

    def auto_and_flag_uids(self) -> list[str]:
        return [e.uid for e in self.entries if e.gate_action in ("auto", "flag")]

    def needs_approval_uids(self) -> list[str]:
        return [e.uid for e in self.entries if e.gate_action == "needs_approval"]


def _plans_dir(project_root: Path | str) -> Path:
    d = Path(project_root) / PLANS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def collection_hash(collection: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(collection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compute_plan_id(
    model_id: str, coll_hash: str, scope_key: str, into: str, engine_version: str = ENGINE_VERSION
) -> str:
    raw = f"{model_id}|{coll_hash}|{scope_key}|{into}|{engine_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compile_plan(
    model: ApiModel,
    report: VerificationReport,
    *,
    collection: dict[str, Any],
    collection_id: str,
    scope_uids: Optional[set[str]] = None,
    into: str = "/",
    generate_tests: bool = False,
    response_style: str = "single",
    overrides: Optional[dict] = None,
    policy: Optional[PolicyConfig] = None,
    project_root: Path | str = ".",
) -> PlanDocument:
    """Build the plan for a scope of endpoints and persist it."""
    endpoints_by_uid: dict[str, Endpoint] = {ep.uid: ep for ep in model.endpoints}
    scope = scope_uids if scope_uids is not None else set(endpoints_by_uid)
    coll_hash = collection_hash(collection)
    scope_key = "all" if scope_uids is None else ",".join(sorted(scope))
    plan_id = compute_plan_id(report.model_id, coll_hash, scope_key, into)

    entries: list[PlanEntry] = []
    rejected: list[dict[str, Any]] = []
    blocked_uids: list[str] = []

    for uid in sorted(scope):
        ep = endpoints_by_uid.get(uid)
        if ep is None:
            continue
        verdict = report.endpoint(uid)
        if verdict is None or not verdict.is_syncable:
            reasons = [f"{f.check}: {f.message}" for f in (verdict.findings if verdict else [])]
            rejected.append({"uid": uid, "verdict": verdict.verdict if verdict else "unknown", "reasons": reasons})
            continue

        score = gate_score(verdict.confidence)
        action = gate_action(score, policy=policy)
        if action == "blocked":
            blocked_uids.append(uid)
            continue

        route: RouteModel = endpoint_to_route_model(ep)
        item = build_request_item(
            route, generate_tests=generate_tests, response_style=response_style, overrides=overrides,
        )
        diff: RequestDiff = merge.compute_diff(collection, item, route, into)

        entries.append(PlanEntry(
            uid=uid, gate_action=action, confidence=verdict.confidence,
            route=route.model_dump(mode="json"), item=item, diff=diff.model_dump(mode="json"), into=into,
        ))

    doc = PlanDocument(
        plan_id=plan_id, model_id=report.model_id, collection_id=collection_id,
        collection_hash=coll_hash, created_at=datetime.now(timezone.utc).isoformat(),
        into_default=into, entries=entries, rejected=rejected, blocked_uids=blocked_uids,
    )
    _save_plan(doc, project_root)
    return doc


def _save_plan(doc: PlanDocument, project_root: Path | str) -> None:
    path = _plans_dir(project_root) / f"{doc.plan_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(doc.model_dump_json(), encoding="utf-8")
    tmp.replace(path)


def load_plan(plan_id: str, project_root: Path | str = ".") -> PlanDocument:
    path = _plans_dir(project_root) / f"{plan_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"No plan with id {plan_id!r} (it may have expired).")
    return PlanDocument.model_validate_json(path.read_text(encoding="utf-8"))


def plan_is_expired(doc: PlanDocument, *, ttl_hours: float = DEFAULT_PLAN_TTL_HOURS) -> bool:
    created = datetime.fromisoformat(doc.created_at)
    age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
    return age_hours > ttl_hours
