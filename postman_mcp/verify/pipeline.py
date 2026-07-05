"""The verification pipeline — V-02 through V-14 over a parsed :class:`ApiModel`.

``V-01`` (schema conformance + size caps) already ran during ingest
(:func:`postman_mcp.model.store.parse_model`) — a document that fails it never reaches
here at all (``ModelIngestError``, the ``BLOCK_MODEL`` verdict).

Pipeline order: structural checks first (cheap, no I/O beyond the model), then the
evidence audit (repo reads + hashing), then identity-set checks, then the witness
engine (the one expensive step, cached by the caller), then cross-checks against it,
then plausibility, then the confidence-sanity pass.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from postman_mcp.confidence.scorer import EndpointAudit, FactAudit, score_endpoint
from postman_mcp.contract.schema import ApiModel, Endpoint, ExtractionMethod, SchemaNode, Traced
from postman_mcp.model.store import compute_model_id
from postman_mcp.models import HTTP_METHODS, normalize_path
from postman_mcp.verify.evidence import audit_evidence
from postman_mcp.verify.report import EndpointVerdict, Finding, VerificationReport, WitnessSummary
from postman_mcp.witness.engine import WitnessSet, build_witness_set

# Registration-site tokens across supported + common custom frameworks (V-07).
_REGISTRATION_SIGNALS = (
    "@app.get(", "@app.post(", "@app.put(", "@app.patch(", "@app.delete(",
    "@router.get(", "@router.post(", "@router.put(", "@router.patch(", "@router.delete(",
    "router.get(", "router.post(", "router.put(", "router.patch(", "router.delete(",
    "@Get(", "@Post(", "@Put(", "@Patch(", "@Delete(", "@Controller(",
    "@GetMapping", "@PostMapping", "@PutMapping", "@PatchMapping", "@DeleteMapping",
    "@RequestMapping", "path(", "re_path(", "@api_view(", "DefaultRouter(",
    "@app.route(", "@bp.get(", "@bp.post(", "register_blueprint(",
    "include_router(", "app.use(", "setGlobalPrefix(",
)

_PLACEHOLDER_PATTERNS = (
    re.compile(r"\{([^}]+)\}"),
    re.compile(r":([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"<(?:[^:>]+:)?([^>]+)>"),
)


def _placeholder_names(path: str) -> list[str]:
    names: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        names.extend(m.group(1) for m in pattern.finditer(path))
    return names


def _walk_schema_refs(node: SchemaNode) -> list[str]:
    refs: list[str] = []
    if node.ref:
        refs.append(node.ref)
    if node.items:
        refs.extend(_walk_schema_refs(node.items))
    for f in node.fields:
        refs.extend(_walk_schema_refs(f))
    return refs


def _add(findings: dict[str, list[Finding]], uid: str, finding: Finding) -> None:
    findings.setdefault(uid, []).append(finding)


def run_pipeline(
    model: ApiModel,
    project_root: Path | str = ".",
    *,
    witness: Optional[WitnessSet] = None,
    repo_commit: Optional[str] = None,
) -> VerificationReport:
    """Run V-02..V-14 over ``model`` and return the full :class:`VerificationReport`."""
    root = Path(project_root)
    model_id = compute_model_id(model)
    is_witness_model = model.generator.provider == "witness"
    commit_for_audit = repo_commit or model.repo.commit

    findings: dict[str, list[Finding]] = {}
    rejected: set[str] = set()
    stale: set[str] = set()
    service_ids = model.service_ids()

    # --- V-02 / V-03 / V-10 (structural, per-endpoint) --------------------------------
    for ep in model.endpoints:
        recomputed = ep.recompute_uid()
        if recomputed != ep.uid:
            _add(findings, ep.uid, Finding(
                check="V-02", severity="info",
                message=f"uid recomputed from {ep.uid!r} to {recomputed!r}; using the recomputed value.",
            ))
            ep.uid = recomputed

        if ep.method.upper() not in HTTP_METHODS:
            _add(findings, ep.uid, Finding(
                check="V-02", severity="reject",
                message=f"Method {ep.method!r} is not a recognized HTTP method.",
            ))
            rejected.add(ep.uid)

        if ep.service not in service_ids:
            _add(findings, ep.uid, Finding(
                check="V-02", severity="reject",
                message=f"Endpoint references undeclared service {ep.service!r}.",
            ))
            rejected.add(ep.uid)

        placeholder_names = set(_placeholder_names(ep.path))
        declared_names = {p.value.name for p in ep.path_params}
        missing_decl = placeholder_names - declared_names
        extra_decl = declared_names - placeholder_names
        if missing_decl or extra_decl:
            _add(findings, ep.uid, Finding(
                check="V-02", severity="reject",
                message=(
                    f"Path placeholders {sorted(missing_decl)} undeclared in path_params; "
                    f"declared-but-unused path_params {sorted(extra_decl)}."
                ),
                detail={"missing": sorted(missing_decl), "extra": sorted(extra_decl)},
            ))
            rejected.add(ep.uid)

        if not ep.identity_evidence:
            _add(findings, ep.uid, Finding(
                check="V-03", severity="reject",
                message="No identity_evidence cited for this endpoint's existence.",
            ))
            rejected.add(ep.uid)

        for traced, name in _facts_with_names(ep):
            if traced is not None and not traced.evidence:
                _add(findings, ep.uid, Finding(
                    check="V-03", severity="warn",
                    message=f"{name} has no cited evidence — capped at ai_inferred confidence.",
                ))

        for traced, name in ((ep.request_body, "request_body"), *[(r, "responses") for r in ep.responses]):
            if traced is None:
                continue
            node = traced.value.schema_
            if node is None:
                continue
            for ref in _walk_schema_refs(node):
                if ref not in model.components:
                    _add(findings, ep.uid, Finding(
                        check="V-10", severity="reject",
                        message=f"{name} references unresolved component ref {ref!r}.",
                    ))
                    rejected.add(ep.uid)

    # --- V-05 duplicate identity -------------------------------------------------------
    by_uid: dict[str, list[Endpoint]] = {}
    for ep in model.endpoints:
        by_uid.setdefault(ep.uid, []).append(ep)
    for uid, group in by_uid.items():
        if len(group) > 1:
            for ep in group:
                other_files = [e.identity_evidence[0].file for e in group if e is not ep and e.identity_evidence]
                _add(findings, uid, Finding(
                    check="V-05", severity="reject",
                    message=f"Duplicate identity {uid!r} — also registered at {other_files}.",
                ))
                rejected.add(uid)

    # --- V-04 / V-14 evidence audit ----------------------------------------------------
    identity_status: dict[str, str] = {}   # uid -> worst verdict among identity evidence
    fact_audits: dict[str, dict[str, FactAudit]] = {}

    for ep in model.endpoints:
        worst = "verified"
        for ev in ep.identity_evidence:
            verdict, detail = audit_evidence(ev, root, repo_commit=commit_for_audit)
            if verdict != "verified":
                check = "V-10" if verdict == "confinement_violation" else "V-04"
                severity = "reject" if verdict in ("fabricated", "confinement_violation", "unreadable") else "warn"
                _add(findings, ep.uid, Finding(
                    check=check, severity=severity,
                    message=f"identity evidence {ev.file}#L{ev.line_start}-{ev.line_end}: {verdict}",
                    detail=detail,
                ))
                if severity == "reject":
                    rejected.add(ep.uid)
                if verdict == "stale":
                    stale.add(ep.uid)
                if _rank(verdict) > _rank(worst):
                    worst = verdict
        identity_status[ep.uid] = worst

        audits: dict[str, FactAudit] = {
            "existence": FactAudit(evidenced=bool(ep.identity_evidence),
                                    all_evidence_verified=(worst == "verified"),
                                    evidence_count=len(ep.identity_evidence), is_identity=True),
            "path": FactAudit(evidenced=bool(ep.identity_evidence),
                               all_evidence_verified=(worst == "verified"),
                               evidence_count=len(ep.identity_evidence), is_identity=True),
        }
        for dim, traced in (("body", ep.request_body), ("auth", ep.auth)):
            if traced is None:
                continue
            audits[dim] = _audit_fact(traced, root, commit_for_audit, findings, ep.uid, dim)
        if ep.responses:
            # Treat the response set as one fact for scoring purposes.
            all_ok = True
            count = 0
            for r in ep.responses:
                fa = _audit_fact(r, root, commit_for_audit, findings, ep.uid, "responses")
                all_ok = all_ok and fa.all_evidence_verified
                count += fa.evidence_count
            audits["responses"] = FactAudit(evidenced=count > 0, all_evidence_verified=all_ok, evidence_count=count)
        fact_audits[ep.uid] = audits

    # --- witness engine + cross-checks (V-07, V-08, V-12, V-13) -----------------------
    witness_set = witness
    witness_crashed = False
    if witness_set is None:
        try:
            witness_set = build_witness_set(root)
        except Exception:  # pragma: no cover - defensive: a witness crash must not block
            witness_set = None
            witness_crashed = True

    agreed = model_only = witness_only = 0
    # (method, file) -> (witness_uid, route) — for matching a model endpoint to a real
    # handler even when its claimed path doesn't compose to the same uid as the witness.
    handler_index: dict[tuple[str, str], tuple[str, object]] = {}
    if witness_set is not None:
        for witness_uid, route in witness_set.by_uid.items():
            ref = route.code_ref or ""
            file_part = ref.split("::", 1)[0]
            if file_part:
                handler_index[(route.method.upper(), Path(file_part).as_posix())] = (witness_uid, route)

    consumed_witness_uids: set[str] = set()  # witness_set.by_uid keys accounted for

    for ep in model.endpoints:
        if ep.uid in rejected:
            continue
        witness_route = witness_set.get(ep.uid) if witness_set is not None else None
        audits = fact_audits[ep.uid]

        if witness_route is not None:
            consumed_witness_uids.add(ep.uid)
            agreed += 1
            audits["existence"].agreement = "agree"
            audits["path"].agreement = "agree"
            if "auth" in audits:
                audits["auth"].agreement = "agree" if witness_route.auth_required == ep.auth.value.required else "disagree"
                if audits["auth"].agreement == "disagree":
                    _add(findings, ep.uid, Finding(
                        check="V-13", severity="warn",
                        message=f"Auth disagreement: model={ep.auth.value.required} witness={witness_route.auth_required}.",
                    ))
            continue

        # No uid match — try handler-level match (same file+method) to distinguish a
        # genuine hallucination (V-07) from a real handler with a differently-composed
        # path (V-12), and to surface any auth disagreement even without a uid match.
        model_only += 1
        candidate_file = None
        if ep.identity_evidence:
            candidate_file = Path(ep.identity_evidence[0].file).as_posix()
        matched = handler_index.get((ep.method.upper(), candidate_file)) if candidate_file else None
        handler_match = matched[1] if matched is not None else None

        if handler_match is not None:
            consumed_witness_uids.add(matched[0])
            model_only -= 1  # a real handler exists; not a pure model-only claim
            agreed += 1
            audits["existence"].agreement = "agree"
            if normalize_path(handler_match.path) != normalize_path(ep.path):
                audits["path"].agreement = "disagree"
                _add(findings, ep.uid, Finding(
                    check="V-12", severity="warn",
                    message=f"Path disagreement: model={ep.path!r} witness={handler_match.path!r}.",
                    detail={"model_path": ep.path, "witness_path": handler_match.path},
                ))
            else:
                audits["path"].agreement = "agree"
            if "auth" in audits:
                audits["auth"].agreement = "agree" if handler_match.auth_required == ep.auth.value.required else "disagree"
            continue

        # Genuinely unmatched — must be evidenced + audited clean + cite a real
        # registration signal, or it's rejected as a hallucination (V-07).
        quotes = " ".join(ev.quote for ev in ep.identity_evidence)
        has_signal = any(sig in quotes for sig in _REGISTRATION_SIGNALS)
        if identity_status.get(ep.uid) != "verified" or not has_signal:
            _add(findings, ep.uid, Finding(
                check="V-07", severity="reject",
                message="No witness match and no audited registration-site signal — rejected as a hallucination.",
            ))
            rejected.add(ep.uid)
        else:
            _add(findings, ep.uid, Finding(
                check="V-07", severity="info",
                message="No witness coverage for this endpoint's framework/path, but identity evidence audited clean.",
            ))
            audits["existence"].agreement = "unavailable"
            audits["path"].agreement = "unavailable"

    if witness_set is not None:
        witness_only = len(witness_set.by_uid) - len(consumed_witness_uids)
        for uid, route in witness_set.by_uid.items():
            if uid in consumed_witness_uids:
                continue
            key = f"__omitted__:{uid}"
            _add(findings, key, Finding(
                check="V-08", severity="warn",
                message=f"Witness found {route.method} {route.path} at {route.code_ref or '?'} — model omits it.",
                detail={"method": route.method, "path": route.path, "code_ref": route.code_ref},
            ))
    if witness_crashed:
        for ep in model.endpoints:
            _add(findings, ep.uid, Finding(
                check="V-07", severity="info",
                message="Witness engine unavailable — cross-checks skipped for this run.",
            ))

    # --- V-06 route conflicts (order-shadowing heuristic) -----------------------------
    _check_conflicts(model, findings)

    # --- V-09 framework plausibility ---------------------------------------------------
    for ep in model.endpoints:
        if ep.request_body is not None and ep.method.upper() in ("GET", "HEAD"):
            _add(findings, ep.uid, Finding(
                check="V-09", severity="warn",
                message=f"Request body declared on {ep.method.upper()} — unusual for this method.",
            ))
        names = _placeholder_names(ep.path)
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            _add(findings, ep.uid, Finding(
                check="V-09", severity="reject",
                message=f"Path parameter name(s) {sorted(dupes)} repeated in {ep.path!r} — ambiguous binding.",
            ))
            rejected.add(ep.uid)

    # --- V-11 confidence sanity (informational only) -----------------------------------
    if not is_witness_model:
        for ep in model.endpoints:
            for traced, name in _facts_with_names(ep):
                if traced is None:
                    continue
                for ev in traced.evidence:
                    if ev.extraction_method not in (ExtractionMethod.AI_INFERRED, ExtractionMethod.WEAK_INFERENCE):
                        _add(findings, ep.uid, Finding(
                            check="V-11", severity="info",
                            message=(
                                f"{name} evidence claims {ev.extraction_method.value!r}; only the MCP can "
                                "promote a fact past ai_inferred — recomputing."
                            ),
                        ))

    # --- assemble the report -----------------------------------------------------------
    endpoints_out: dict[str, EndpointVerdict] = {}
    for ep in model.endpoints:
        ep_findings = findings.get(ep.uid, [])
        if ep.uid in rejected:
            verdict = "reject"
            confidence: dict[str, int] = {}
        else:
            audit = EndpointAudit(
                generator_is_witness=is_witness_model,
                existence=fact_audits[ep.uid]["existence"],
                path=fact_audits[ep.uid]["path"],
                body=fact_audits[ep.uid].get("body"),
                auth=fact_audits[ep.uid].get("auth"),
                responses=fact_audits[ep.uid].get("responses"),
            )
            confidence = score_endpoint(audit)
            if ep.uid in stale:
                verdict = "stale"
            elif any(f.severity == "warn" for f in ep_findings):
                verdict = "warn"
            else:
                verdict = "pass"
        endpoints_out[ep.uid] = EndpointVerdict(
            uid=ep.uid, verdict=verdict, findings=ep_findings, confidence=confidence,
        )

    # Surface omission findings (not tied to a model endpoint) under their own keys.
    for key, flist in findings.items():
        if key.startswith("__omitted__:"):
            endpoints_out[key] = EndpointVerdict(uid=key, verdict="warn", findings=flist, confidence={})

    if any(v.verdict == "reject" for v in endpoints_out.values()):
        model_verdict = "endpoints_rejected"
    elif any(v.verdict in ("warn", "stale") for v in endpoints_out.values()):
        model_verdict = "ok_with_warnings"
    else:
        model_verdict = "ok"

    n_pass = sum(1 for v in endpoints_out.values() if v.verdict == "pass")
    n_warn = sum(1 for v in endpoints_out.values() if v.verdict == "warn")
    n_reject = sum(1 for v in endpoints_out.values() if v.verdict == "reject")
    n_stale = sum(1 for v in endpoints_out.values() if v.verdict == "stale")
    summary = (
        f"{len(model.endpoints)} endpoint(s): {n_pass} verified, {n_warn} warned, "
        f"{n_reject} rejected, {n_stale} stale."
    )
    if witness_only > 0:
        summary += f" {witness_only} witness-only route(s) omitted from the model."

    return VerificationReport(
        model_id=model_id,
        verdict=model_verdict,
        endpoints=endpoints_out,
        witness=WitnessSummary(agreed=agreed, model_only=max(model_only, 0), witness_only=max(witness_only, 0)),
        summary=summary,
    )


_VERDICT_RANK = {"verified": 0, "stale": 1, "unreadable": 2, "confinement_violation": 3, "fabricated": 4}


def _rank(verdict: str) -> int:
    return _VERDICT_RANK.get(verdict, 4)


def _facts_with_names(ep: Endpoint):
    return (
        (ep.operation_id, "operation_id"),
        (ep.summary, "summary"),
        (ep.description, "description"),
        (ep.tags, "tags"),
        (ep.folder, "folder"),
        (ep.request_body, "request_body"),
        (ep.auth, "auth"),
        (ep.examples, "examples"),
        (ep.versioning, "versioning"),
    )


def _audit_fact(
    traced: Traced,
    root: Path,
    commit: Optional[str],
    findings: dict[str, list[Finding]],
    uid: str,
    name: str,
) -> FactAudit:
    if not traced.evidence:
        return FactAudit(evidenced=False, all_evidence_verified=True, evidence_count=0)
    all_ok = True
    for ev in traced.evidence:
        verdict, detail = audit_evidence(ev, root, repo_commit=commit)
        if verdict != "verified":
            all_ok = False
            check = "V-10" if verdict == "confinement_violation" else "V-04"
            _add(findings, uid, Finding(
                check=check, severity="warn",
                message=f"{name} evidence {ev.file}#L{ev.line_start}-{ev.line_end}: {verdict}",
                detail=detail,
            ))
    return FactAudit(evidenced=True, all_evidence_verified=all_ok, evidence_count=len(traced.evidence))


def _check_conflicts(model: ApiModel, findings: dict[str, list[Finding]]) -> None:
    """V-06 — heuristic order-shadowing within the same file."""
    by_file_method: dict[tuple[str, str], list[Endpoint]] = {}
    for ep in model.endpoints:
        if not ep.identity_evidence:
            continue
        key = (ep.identity_evidence[0].file, ep.method.upper())
        by_file_method.setdefault(key, []).append(ep)

    for group in by_file_method.values():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            a_segs = [s for s in a.path.strip("/").split("/") if s]
            for b in group[i + 1:]:
                b_segs = [s for s in b.path.strip("/").split("/") if s]
                if len(a_segs) != len(b_segs):
                    continue
                diff_positions = [
                    idx for idx, (sa, sb) in enumerate(zip(a_segs, b_segs)) if sa != sb
                ]
                if len(diff_positions) != 1:
                    continue
                idx = diff_positions[0]
                a_is_param = a_segs[idx].startswith("{") or a_segs[idx].startswith(":") or a_segs[idx].startswith("<")
                b_is_param = b_segs[idx].startswith("{") or b_segs[idx].startswith(":") or b_segs[idx].startswith("<")
                if a_is_param != b_is_param:
                    _add(findings, a.uid, Finding(
                        check="V-06", severity="warn",
                        message=f"Possible route shadowing with {b.path!r} depending on registration order.",
                    ))
                    _add(findings, b.uid, Finding(
                        check="V-06", severity="warn",
                        message=f"Possible route shadowing with {a.path!r} depending on registration order.",
                    ))
