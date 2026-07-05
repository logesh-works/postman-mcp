"""The verification pipeline — the adversarial corpus.

Every check gets at least one hand-built model designed to trip it, plus one clean
model that must pass — mirroring how ``test_accuracy.py`` treats the parsers' recall/
precision as an enforced number rather than a claim.
"""

from __future__ import annotations

import hashlib

import pytest

from postman_mcp.config.store import ProjectConfig
from postman_mcp.contract.schema import (
    ApiModel,
    Body,
    Endpoint,
    Evidence,
    ExtractionMethod,
    GeneratorInfo,
    ParamValue,
    SchemaNode,
    Service,
    Traced,
)
from postman_mcp.verify.pipeline import run_pipeline

FASTAPI_APP = '''
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class PaymentRequest(BaseModel):
    amount: int
    currency: str


@app.post("/payments")
def create_payment(body: PaymentRequest):
    """Create a payment."""
    return {}
'''


@pytest.fixture
def project(tmp_path):
    (tmp_path / "app.py").write_text(FASTAPI_APP, encoding="utf-8")
    return tmp_path


def _hash(*lines: str) -> str:
    return hashlib.sha256("\n".join(l.rstrip() for l in lines).encode("utf-8")).hexdigest()


def _real_evidence(project, symbol="create_payment") -> Evidence:
    text = (project / "app.py").read_text().splitlines()
    for idx, line in enumerate(text):
        if symbol in line:
            return Evidence(
                file="app.py", line_start=idx + 1, line_end=idx + 1, symbol=symbol,
                extraction_method=ExtractionMethod.AI_INFERRED,
                snippet_sha256=_hash(line), quote=line.strip()[:200],
            )
    raise AssertionError(f"{symbol} not found in fixture")


def _decorator_evidence(project, contains="@app.post") -> Evidence:
    """Cite the registration-site line itself (contains a real V-07 signal token)."""
    text = (project / "app.py").read_text().splitlines()
    for idx, line in enumerate(text):
        if contains in line:
            return Evidence(
                file="app.py", line_start=idx + 1, line_end=idx + 1,
                extraction_method=ExtractionMethod.AI_INFERRED,
                snippet_sha256=_hash(line), quote=line.strip()[:200],
            )
    raise AssertionError(f"{contains!r} not found in fixture")


def _model(*endpoints: Endpoint, commit=None) -> ApiModel:
    return ApiModel(
        generator=GeneratorInfo(provider="claude", model="test"),
        repo={"commit": commit} if commit else {},
        services=[Service(id="default")],
        endpoints=list(endpoints),
    )


# --- V-07 hallucination -------------------------------------------------------------


def test_hallucinated_endpoint_is_rejected(project):
    fake = Endpoint(
        uid="default:GET:/admin/stats", service="default", method="GET", path="/admin/stats",
        identity_evidence=[Evidence(
            file="app.py", line_start=1, line_end=1, symbol="create_payment",
            snippet_sha256="0" * 64, quote="totally made up",
        )],
    )
    report = run_pipeline(_model(fake), project)
    assert report.verdict == "endpoints_rejected"
    assert report.endpoints[fake.uid].verdict == "reject"
    assert any(f.check == "V-07" for f in report.endpoints[fake.uid].findings)


def test_valid_witness_matched_endpoint_passes(project):
    ev = _real_evidence(project)
    ep = Endpoint(
        uid="default:POST:/payments", service="default", method="POST", path="/payments",
        identity_evidence=[ev],
    )
    report = run_pipeline(_model(ep), project)
    assert report.endpoints[ep.uid].verdict in ("pass", "warn")
    assert report.endpoints[ep.uid].confidence["existence"] >= 90
    assert report.witness.agreed == 1


# --- V-05 duplicate identity ----------------------------------------------------------


def test_duplicate_identity_rejects_both(project):
    ev = _real_evidence(project)
    a = Endpoint(uid="default:POST:/payments", service="default", method="POST", path="/payments",
                 identity_evidence=[ev])
    b = Endpoint(uid="default:POST:/payments", service="default", method="POST", path="/payments",
                 identity_evidence=[ev])
    report = run_pipeline(_model(a, b), project)
    assert report.endpoints[a.uid].verdict == "reject"
    # Both endpoints share a uid, so only one entry exists in the report dict — but it
    # must carry a V-05 finding either way.
    assert any(f.check == "V-05" for f in report.endpoints[a.uid].findings)


# --- V-02 path/param mismatch -----------------------------------------------------------


def test_path_placeholder_without_declared_param_is_rejected(project):
    ev = _real_evidence(project)
    ep = Endpoint(
        uid="default:GET:/payments/{id}", service="default", method="GET", path="/payments/{id}",
        identity_evidence=[ev],  # no path_params declared for {id}
    )
    report = run_pipeline(_model(ep), project)
    assert report.endpoints[ep.uid].verdict == "reject"
    assert any(f.check == "V-02" for f in report.endpoints[ep.uid].findings)


def test_duplicate_path_param_name_is_rejected(project):
    ev = _real_evidence(project)
    ep = Endpoint(
        uid="default:GET:/x/{id}/y/{id}", service="default", method="GET", path="/x/{id}/y/{id}",
        identity_evidence=[ev],
        path_params=[Traced(value=ParamValue(name="id", location="path", required=True))],
    )
    report = run_pipeline(_model(ep), project)
    assert report.endpoints[ep.uid].verdict == "reject"
    assert any(f.check == "V-09" for f in report.endpoints[ep.uid].findings)


# --- V-10 reference resolution / path confinement ---------------------------------------


def test_dangling_component_ref_is_rejected(project):
    ev = _real_evidence(project)
    ep = Endpoint(
        uid="default:POST:/payments", service="default", method="POST", path="/payments",
        identity_evidence=[ev],
        request_body=Traced(
            value=Body(schema=SchemaNode(type="object", fields=[
                SchemaNode(type="object", field_name="nested", ref="components.DoesNotExist"),
            ])),
            confidence=0.5, evidence=[ev],
        ),
    )
    report = run_pipeline(_model(ep), project)
    assert report.endpoints[ep.uid].verdict == "reject"
    assert any(f.check == "V-10" for f in report.endpoints[ep.uid].findings)


def test_path_traversal_evidence_is_rejected(project):
    ep = Endpoint(
        uid="default:GET:/secret", service="default", method="GET", path="/secret",
        identity_evidence=[Evidence(
            file="../outside.py", line_start=1, line_end=1, snippet_sha256="a" * 64,
        )],
    )
    report = run_pipeline(_model(ep), project)
    assert report.endpoints[ep.uid].verdict == "reject"
    checks = {f.check for f in report.endpoints[ep.uid].findings}
    assert "V-10" in checks


# --- V-09 plausibility -----------------------------------------------------------------


def test_body_on_get_is_warned(project):
    ev = _decorator_evidence(project)
    ep = Endpoint(
        uid="default:GET:/payments", service="default", method="GET", path="/payments",
        identity_evidence=[ev],
        request_body=Traced(value=Body(schema=SchemaNode(type="object")), confidence=0.5, evidence=[ev]),
    )
    report = run_pipeline(_model(ep), project)
    verdict = report.endpoints[ep.uid]
    assert verdict.verdict != "reject"
    assert any(f.check == "V-09" and f.severity == "warn" for f in verdict.findings)


# --- V-08 omission -----------------------------------------------------------------------


def test_omitted_witness_route_is_flagged(project):
    """A model that omits a real route the witness engine found gets a V-08 warning."""
    report = run_pipeline(_model(), project)
    omitted_keys = [k for k in report.endpoints if k.startswith("__omitted__:")]
    assert omitted_keys, "expected the real /payments route to be flagged as omitted"
    assert report.witness.witness_only == 1


# --- V-04 fabricated vs V-14 stale -------------------------------------------------------


def test_hash_mismatch_with_no_declared_commit_is_stale_not_fabricated(project):
    ev = _real_evidence(project)
    ev.snippet_sha256 = "f" * 64  # wrong hash, no repo.commit declared
    ep = Endpoint(
        uid="default:POST:/payments", service="default", method="POST", path="/payments",
        identity_evidence=[ev],
    )
    report = run_pipeline(_model(ep), project)
    # No witness match possible (evidence audit already fails) → treated conservatively.
    findings = report.endpoints[ep.uid].findings
    assert any(f.check == "V-04" and "stale" in f.message for f in findings)


# --- witness engine unavailable degrades gracefully, never silently promotes -----------


def test_manual_witness_none_still_runs(project):
    """An endpoint with no witness coverage must not crash, and must not over-trust."""
    from postman_mcp.witness.engine import WitnessSet

    empty_witness = WitnessSet([], [], [])
    ev = _decorator_evidence(project)
    ep = Endpoint(
        uid="default:POST:/payments", service="default", method="POST", path="/payments",
        identity_evidence=[ev],
    )
    report = run_pipeline(_model(ep), project, witness=empty_witness)
    # No witness coverage, but audited clean + real registration signal → allowed through,
    # capped at framework_verified rather than promoted to ast_verified.
    v = report.endpoints[ep.uid]
    assert v.verdict != "reject"
    assert v.confidence["existence"] == 90
