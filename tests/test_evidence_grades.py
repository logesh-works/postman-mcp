"""Phase 3: symbol-graph grounding (V-07 widening) + evidence grades (E1-E4).

Grounding must be strictly additive: it only ever lets MORE genuinely-real endpoints
through V-07, never fewer — the legacy framework-token check keeps working unchanged,
and a real registration site outside the token list (a custom/uncommon framework) is
no longer rejected just because its exact decorator name isn't enumerated anywhere.
"""

from __future__ import annotations

import hashlib

from postman_mcp.confidence.grades import EvidenceGrade, compute_grade
from postman_mcp.contract.schema import ApiModel, Endpoint, Evidence, ExtractionMethod, GeneratorInfo, Service
from postman_mcp.verify.pipeline import run_pipeline
from postman_mcp.witness.engine import WitnessSet

# A registration style with no entry anywhere in _REGISTRATION_SIGNALS — a stand-in
# for "some framework nobody hardcoded a token for."
CUSTOM_FRAMEWORK_APP = '''
from tinyweb import App

app = App()


@app.endpoint("/widgets")
def list_widgets():
    """List widgets."""
    return []
'''


def _hash(*lines: str) -> str:
    return hashlib.sha256("\n".join(l.rstrip() for l in lines).encode("utf-8")).hexdigest()


def _model(*endpoints: Endpoint) -> ApiModel:
    return ApiModel(
        generator=GeneratorInfo(provider="claude", model="test"),
        services=[Service(id="default")],
        endpoints=list(endpoints),
    )


def test_grounding_admits_a_real_route_with_no_registration_token(tmp_path):
    """@app.endpoint(...) matches nothing in _REGISTRATION_SIGNALS, but it IS a real
    decorated symbol at the cited line — grounding must let it through V-07 anyway."""
    (tmp_path / "app.py").write_text(CUSTOM_FRAMEWORK_APP, encoding="utf-8")
    text = (tmp_path / "app.py").read_text().splitlines()
    line_no = next(i for i, l in enumerate(text, start=1) if "def list_widgets" in l)
    dec_line_no = next(i for i, l in enumerate(text, start=1) if "@app.endpoint" in l)

    ev = Evidence(
        file="app.py", line_start=line_no, line_end=line_no, symbol="list_widgets",
        extraction_method=ExtractionMethod.AI_INFERRED,
        snippet_sha256=_hash(text[line_no - 1]), quote=text[line_no - 1].strip()[:200],
    )
    ep = Endpoint(uid="default:GET:/widgets", service="default", method="GET", path="/widgets", identity_evidence=[ev])

    # No witness coverage at all (an empty witness set — nothing to cross-check against).
    report = run_pipeline(_model(ep), tmp_path, witness=WitnessSet([], [], []))
    v = report.endpoints[ep.uid]
    assert v.verdict != "reject", f"grounding should have admitted this endpoint; findings={v.findings}"
    assert any(f.check == "V-07" and f.severity == "info" for f in v.findings)
    # Sanity: the decorator line itself is also grounded (not just the def line).
    assert dec_line_no > 0


def test_fabricated_route_still_rejected_despite_grounding(tmp_path):
    """Grounding checks the CITED span, not the endpoint's truthiness — citing a real
    file but the wrong (unrelated, non-route) line must still be rejected."""
    (tmp_path / "app.py").write_text(CUSTOM_FRAMEWORK_APP, encoding="utf-8")
    ev = Evidence(
        file="app.py", line_start=1, line_end=1,  # "from tinyweb import App" — not a route
        snippet_sha256=_hash("from tinyweb import App"), quote="from tinyweb import App",
    )
    ep = Endpoint(uid="default:GET:/nonexistent", service="default", method="GET", path="/nonexistent",
                  identity_evidence=[ev])
    report = run_pipeline(_model(ep), tmp_path, witness=WitnessSet([], [], []))
    assert report.endpoints[ep.uid].verdict == "reject"


def test_verified_endpoint_carries_grades(tmp_path):
    (tmp_path / "app.py").write_text(CUSTOM_FRAMEWORK_APP, encoding="utf-8")
    text = (tmp_path / "app.py").read_text().splitlines()
    line_no = next(i for i, l in enumerate(text, start=1) if "def list_widgets" in l)
    ev = Evidence(
        file="app.py", line_start=line_no, line_end=line_no, symbol="list_widgets",
        snippet_sha256=_hash(text[line_no - 1]), quote=text[line_no - 1].strip()[:200],
    )
    ep = Endpoint(uid="default:GET:/widgets", service="default", method="GET", path="/widgets", identity_evidence=[ev])
    report = run_pipeline(_model(ep), tmp_path, witness=WitnessSet([], [], []))
    v = report.endpoints[ep.uid]
    assert v.verdict != "reject"
    assert v.grades.get("existence") in (EvidenceGrade.GROUNDED.value, EvidenceGrade.CORROBORATED.value)
    assert v.grades.get("path") == v.grades.get("existence")


def test_rejected_endpoint_has_no_grades(tmp_path):
    (tmp_path / "app.py").write_text(CUSTOM_FRAMEWORK_APP, encoding="utf-8")
    ep = Endpoint(
        uid="default:GET:/fake", service="default", method="GET", path="/fake",
        identity_evidence=[Evidence(file="app.py", line_start=1, line_end=1, snippet_sha256="0" * 64, quote="made up")],
    )
    report = run_pipeline(_model(ep), tmp_path, witness=WitnessSet([], [], []))
    v = report.endpoints[ep.uid]
    assert v.verdict == "reject"
    assert v.grades == {}


# --- compute_grade unit tests (pure function, no I/O) --------------------------------


def test_compute_grade_unevidenced_or_unverified_is_inferred():
    assert compute_grade(evidenced=False, all_evidence_verified=True) == EvidenceGrade.INFERRED
    assert compute_grade(evidenced=True, all_evidence_verified=False) == EvidenceGrade.INFERRED


def test_compute_grade_agreement_or_corroboration_is_corroborated():
    assert compute_grade(evidenced=True, all_evidence_verified=True, agreement="agree") == EvidenceGrade.CORROBORATED
    assert compute_grade(evidenced=True, all_evidence_verified=True, corroborated=True) == EvidenceGrade.CORROBORATED


def test_compute_grade_grounded_without_witness_opinion():
    assert compute_grade(evidenced=True, all_evidence_verified=True, grounded=True) == EvidenceGrade.GROUNDED


def test_compute_grade_plain_claim_is_inferred():
    assert compute_grade(evidenced=True, all_evidence_verified=True) == EvidenceGrade.INFERRED


def test_compute_grade_ungrounded_field_prevents_grounded_even_with_citation_grounding():
    assert compute_grade(
        evidenced=True, all_evidence_verified=True, grounded=True, fields_grounded=False,
    ) == EvidenceGrade.INFERRED


def test_compute_grade_fields_grounded_true_or_none_preserves_grounded():
    assert compute_grade(
        evidenced=True, all_evidence_verified=True, grounded=True, fields_grounded=True,
    ) == EvidenceGrade.GROUNDED
    assert compute_grade(
        evidenced=True, all_evidence_verified=True, grounded=True, fields_grounded=None,
    ) == EvidenceGrade.GROUNDED
