"""The confidence scorer — a pure function of evidence class + agreement."""

from __future__ import annotations

from postman_mcp.confidence.policy import PolicyConfig, gate_action
from postman_mcp.confidence.scorer import EndpointAudit, FactAudit, gate_score, score_endpoint


def _audit(**overrides) -> EndpointAudit:
    return EndpointAudit(generator_is_witness=False, **overrides)


def test_witness_produced_identity_scores_ast_verified():
    audit = EndpointAudit(generator_is_witness=True)
    scores = score_endpoint(audit)
    assert scores["existence"] == 95 and scores["path"] == 95


def test_witness_agreement_promotes_llm_claim_to_ast_verified():
    audit = _audit(
        existence=FactAudit(evidenced=True, all_evidence_verified=True, agreement="agree", is_identity=True),
        path=FactAudit(evidenced=True, all_evidence_verified=True, agreement="agree", is_identity=True),
    )
    scores = score_endpoint(audit)
    assert scores["existence"] == 95
    assert scores["path"] == 95


def test_witness_disagreement_floors_at_50():
    audit = _audit(
        existence=FactAudit(evidenced=True, all_evidence_verified=True, agreement="agree", is_identity=True),
        path=FactAudit(evidenced=True, all_evidence_verified=True, agreement="disagree", is_identity=True),
    )
    scores = score_endpoint(audit)
    assert scores["path"] == 50


def test_audited_only_no_witness_caps_identity_at_90():
    audit = _audit(
        existence=FactAudit(evidenced=True, all_evidence_verified=True, agreement="unavailable", is_identity=True),
        path=FactAudit(evidenced=True, all_evidence_verified=True, agreement="unavailable", is_identity=True),
    )
    scores = score_endpoint(audit)
    assert scores["existence"] == 90 and scores["path"] == 90


def test_unevidenced_fact_caps_at_ai_inferred_50():
    audit = _audit(body=FactAudit(evidenced=False, all_evidence_verified=True))
    scores = score_endpoint(audit)
    assert scores["body"] == 50


def test_failed_audit_floors_at_weak_inference_25():
    audit = _audit(body=FactAudit(evidenced=True, all_evidence_verified=False, evidence_count=1))
    scores = score_endpoint(audit)
    assert scores["body"] == 25


def test_multi_source_agreement_without_witness_scores_75():
    audit = _audit(
        body=FactAudit(evidenced=True, all_evidence_verified=True, evidence_count=2, agreement="unavailable")
    )
    scores = score_endpoint(audit)
    assert scores["body"] == 75


def test_gate_score_is_min_of_existence_and_path():
    assert gate_score({"existence": 95, "path": 60, "body": 90}) == 60


def test_gate_action_thresholds():
    policy = PolicyConfig()
    assert gate_action(95, policy=policy) == "auto"
    assert gate_action(80, policy=policy) == "flag"
    assert gate_action(60, policy=policy) == "needs_approval"
    assert gate_action(10, policy=policy) == "blocked"


def test_allow_low_confidence_opts_a_blocked_score_into_needs_approval():
    policy = PolicyConfig(allow_low_confidence=True)
    assert gate_action(10, policy=policy) == "needs_approval"
    # Still requires explicit apply(approve=[...]) — never promoted to "auto"/"flag".
    assert gate_action(10, policy=PolicyConfig(allow_low_confidence=False)) == "blocked"


def test_gate_action_respects_custom_policy():
    policy = PolicyConfig(auto_threshold=99, flag_threshold=95, approval_threshold=90)
    assert gate_action(96, policy=policy) == "flag"
