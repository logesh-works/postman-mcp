"""The confidence scorer — a pure function of evidence class + agreement.

``Traced.confidence`` (the LLM's own suggestion) is never read here. Every score is
derived from: the evidence class actually earned (starting at ``ai_inferred`` for any
non-witness submission), whether the independent witness engine agrees, and whether
every cited evidence item survived the audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from postman_mcp.contract.schema import CLASS_CAP, ExtractionMethod

Agreement = Literal["agree", "disagree", "unavailable"]


@dataclass
class FactAudit:
    """What the pipeline learned about one fact (existence/path/body/auth/responses)."""

    evidenced: bool = False
    all_evidence_verified: bool = True   # False if any cited evidence failed audit
    evidence_count: int = 0
    agreement: Agreement = "unavailable"
    is_identity: bool = False
    fields_grounded_ratio: float = 1.0   # grounded+unknown / claimed; 1.0 = n/a or fully grounded


@dataclass
class EndpointAudit:
    """Everything the scorer needs for one endpoint, gathered by the pipeline."""

    generator_is_witness: bool
    existence: FactAudit = field(default_factory=lambda: FactAudit(is_identity=True))
    path: FactAudit = field(default_factory=lambda: FactAudit(is_identity=True))
    body: Optional[FactAudit] = None
    auth: Optional[FactAudit] = None
    responses: Optional[FactAudit] = None


_AGREEMENT_BONUS = 5
_DISAGREEMENT_SCORE = 50
_AUDIT_PENALTY = 15
_FIELD_PENALTY_FLOOR = 0.5  # worst case (ratio=0) halves the score; never zeroes it


def _score_fact(fact: FactAudit, *, generator_is_witness: bool) -> int:
    if not fact.all_evidence_verified:
        # Any failed citation on a non-identity fact — floor to weak inference.
        return CLASS_CAP[ExtractionMethod.WEAK_INFERENCE]

    if fact.agreement == "disagree":
        return _DISAGREEMENT_SCORE

    if generator_is_witness:
        # The witness engine's own claims: identity → ast_verified, everything else →
        # framework_verified (the parsers' body/auth/response extraction is heuristic,
        # not a full type oracle, so it doesn't earn the top tier on its own say-so).
        base_class = (
            ExtractionMethod.AST_VERIFIED if fact.is_identity else ExtractionMethod.FRAMEWORK_VERIFIED
        )
        base = CLASS_CAP[base_class]
    elif fact.agreement == "agree":
        promoted = ExtractionMethod.AST_VERIFIED if fact.is_identity else ExtractionMethod.FRAMEWORK_VERIFIED
        base = min(CLASS_CAP[promoted], CLASS_CAP[promoted] + _AGREEMENT_BONUS)
    elif not fact.evidenced:
        # No witness opinion available — audited-only tiers.
        base = CLASS_CAP[ExtractionMethod.AI_INFERRED]
    elif fact.is_identity:
        base = CLASS_CAP[ExtractionMethod.FRAMEWORK_VERIFIED]
    elif fact.evidence_count >= 2:
        base = CLASS_CAP[ExtractionMethod.MULTI_SOURCE_INFERRED]
    else:
        base = CLASS_CAP[ExtractionMethod.AI_INFERRED]

    if fact.fields_grounded_ratio < 1.0:
        # Graduated, not binary: a body with most fields grounded loses little; a
        # body with none grounded loses half, never all of it — legitimate dynamic
        # bodies (dict/**kwargs) exist and must not be punished as hard as a wrong
        # citation (which already floors at WEAK_INFERENCE above, unconditionally).
        base = round(base * (_FIELD_PENALTY_FLOOR + (1 - _FIELD_PENALTY_FLOOR) * fact.fields_grounded_ratio))
    return base


def score_endpoint(audit: EndpointAudit) -> dict[str, int]:
    """Compute the per-dimension confidence dict the report and diff both show."""
    scores: dict[str, int] = {
        "existence": _score_fact(audit.existence, generator_is_witness=audit.generator_is_witness),
        "path": _score_fact(audit.path, generator_is_witness=audit.generator_is_witness),
    }
    if audit.body is not None:
        scores["body"] = _score_fact(audit.body, generator_is_witness=audit.generator_is_witness)
    if audit.auth is not None:
        scores["auth"] = _score_fact(audit.auth, generator_is_witness=audit.generator_is_witness)
    if audit.responses is not None:
        scores["responses"] = _score_fact(audit.responses, generator_is_witness=audit.generator_is_witness)
    return scores


def gate_score(scores: dict[str, int]) -> int:
    """The endpoint-level gate score — ``min(existence, path)``."""
    return min(scores.get("existence", 0), scores.get("path", 0))
