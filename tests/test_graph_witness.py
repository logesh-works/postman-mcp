"""Graph witness + compare/migration tooling (Phase 2).

Uses the same FastAPI fixture as ``test_witness_engine.py`` so the parser witness
(V2) and graph witness (V3) can be compared over identical ground truth.
"""

from __future__ import annotations

import textwrap

from postman_mcp.config.store import ProjectConfig
from postman_mcp.service.compare import compare_engines, validate_migration
from postman_mcp.verify.candidates import is_grounded_evidence
from postman_mcp.verify.graph_witness import build_graph_witness
from postman_mcp.witness.engine import build_witness_set
from tests.benchmark_corpus import CORPUS

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


def _project(tmp_path):
    (tmp_path / "app.py").write_text(FASTAPI_APP, encoding="utf-8")
    return tmp_path


def test_graph_witness_finds_decorated_route(tmp_path):
    project = _project(tmp_path)
    ws = build_graph_witness(project)
    assert len(ws.routes) == 1
    assert ws.routes[0].method == "POST"
    assert ws.routes[0].path == "/payments"
    assert ws.routes[0].code_ref and "app.py" in ws.routes[0].code_ref
    assert ws.routes[0].auth_required is False  # miner asserts no auth claim


def test_graph_witness_skips_verbless_generic_hits(tmp_path):
    (tmp_path / "urls.py").write_text(
        'from django.urls import path\nurlpatterns = [path("things/", views.list_things)]\n',
        encoding="utf-8",
    )
    ws = build_graph_witness(tmp_path)
    # "path(" alone carries no verb — never asserted as a route identity.
    assert all(r.method for r in ws.routes)


def test_compare_engines_reports_agreement(tmp_path):
    project = _project(tmp_path)
    report = compare_engines(project, config=ProjectConfig(framework="fastapi", inputMode="code"))
    assert "agreed: 1" in report
    assert "Full agreement." in report


def test_validate_migration_passes_when_graph_covers_parser(tmp_path):
    project = _project(tmp_path)
    report = validate_migration(project, config=ProjectConfig(framework="fastapi", inputMode="code"))
    assert "PASS" in report
    assert "route recall 100%" in report


def test_validate_migration_fails_on_django_viewset_dispatch(tmp_path):
    """Django's ViewSet.as_view({"get": "list"}) method-mapping carries no HTTP verb
    at the registration site at all — a known, documented static-analysis gap (see
    tests/benchmark_retrieval.py) the graph witness cannot see. The parser resolves
    it fully, so this is a genuine, deterministic FAIL naming the missed routes."""
    files, _expected = CORPUS["django"]
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    report = validate_migration(tmp_path, config=ProjectConfig(framework="django", inputMode="code"))
    assert "FAIL" in report
    assert "Missing from graph witness" in report


def test_is_grounded_evidence_true_for_real_decorator_false_for_fabricated(tmp_path):
    from postman_mcp.index import build_index

    project = _project(tmp_path)
    index = build_index(project)
    lines = (project / "app.py").read_text().splitlines()
    decorator_line = next(i for i, l in enumerate(lines, start=1) if "@app.post" in l)

    assert is_grounded_evidence(index, "app.py", decorator_line, decorator_line) is True
    assert is_grounded_evidence(index, "app.py", 9999, 9999) is False
