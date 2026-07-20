"""Evidence grades (E1-E4) — see ``docs/architecture/v3-proposal.md`` § verification.

A coarser, four-tier view of the same audit information ``confidence/scorer.py``
already computes, expressed in the vocabulary the V3 proposal defines:

- **E1 EXECUTED** — observed from runtime introspection/probing. Not reachable in
  this phase: there is no runtime-evidence layer yet (see the proposal's Layer 3,
  explicitly opt-in and later). Stated honestly here rather than left implicit.
- **E2 CORROBORATED** — an independent, human-authored witness agrees: the parser or
  graph witness, or the evidence corpus (a test URL, an OpenAPI path, an existing
  Postman collection entry) naming the same route.
- **E3 GROUNDED** — every citation audits clean AND the cited span is a real
  symbol/candidate in the repo's own structure — mechanically anchored, but no
  independent witness has an opinion.
- **E4 INFERRED** — a citation exists and audits clean, but nothing beyond the
  producer's own claim backs it (or there is no evidence at all).

Grades never gate a sync on their own — ``confidence/scorer.py`` and
``confidence/policy.py`` still own that. This is a readability/trust layer surfaced
per fact in the verification report, letting a reader see *which* facts are backed by
more than an unverified claim, without re-deriving it from the raw findings.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class EvidenceGrade(str, Enum):
    EXECUTED = "E1"
    CORROBORATED = "E2"
    GROUNDED = "E3"
    INFERRED = "E4"


def compute_grade(
    *,
    evidenced: bool,
    all_evidence_verified: bool,
    agreement: str = "unavailable",
    corroborated: bool = False,
    grounded: bool = False,
    fields_grounded: Optional[bool] = None,
) -> EvidenceGrade:
    """Pure function over inputs the pipeline already computes (or cheaply derives).
    No LLM involved — deterministic, mechanical classification only.

    ``fields_grounded`` narrows GROUNDED for facts with claimed schema fields
    (body/responses): ``None`` (not applicable — no fields were claimed, or this
    fact isn't a schema fact) and ``True`` behave exactly as before; only a
    confident ``False`` (a claimed field the repo's own class structure doesn't
    have) prevents the citation-only grounding from earning E3 on its own.
    """
    if not evidenced or not all_evidence_verified:
        return EvidenceGrade.INFERRED
    if agreement == "agree" or corroborated:
        return EvidenceGrade.CORROBORATED
    if grounded and fields_grounded is not False:
        return EvidenceGrade.GROUNDED
    return EvidenceGrade.INFERRED
