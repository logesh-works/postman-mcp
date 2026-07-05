"""The Witness Engine — the demoted parsers as an independent oracle + fallback producer."""

from __future__ import annotations

from postman_mcp.config.store import ProjectConfig
from postman_mcp.model.adapter import endpoint_to_route_model
from postman_mcp.witness.engine import build_witness_set, witness_to_apim

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


def test_build_witness_set_finds_the_route(tmp_path):
    project = _project(tmp_path)
    ws = build_witness_set(project, ProjectConfig(framework="fastapi", inputMode="code"))
    assert len(ws.routes) == 1
    assert ws.routes[0].method == "POST"
    assert ws.routes[0].path == "/payments"


def test_witness_to_apim_produces_real_evidence(tmp_path):
    project = _project(tmp_path)
    ws = build_witness_set(project, ProjectConfig(framework="fastapi", inputMode="code"))
    apim = witness_to_apim(ws, project_root=project)

    assert apim.generator.provider == "witness"
    ep = apim.endpoints[0]
    assert ep.uid == "default:POST:/payments"
    ev = ep.identity_evidence[0]
    assert ev.file == "app.py"
    cited_line = (project / "app.py").read_text().splitlines()[ev.line_start - 1]
    assert ev.symbol in cited_line

    # The hash actually matches what's on disk — not a placeholder.
    import hashlib
    expected = hashlib.sha256(cited_line.rstrip().encode("utf-8")).hexdigest()
    assert ev.snippet_sha256 == expected


def test_witness_endpoint_adapts_back_to_route_model(tmp_path):
    project = _project(tmp_path)
    ws = build_witness_set(project, ProjectConfig(framework="fastapi", inputMode="code"))
    apim = witness_to_apim(ws, project_root=project)
    route = endpoint_to_route_model(apim.endpoints[0])
    assert route.method == "POST"
    assert route.path == "/payments"
    assert route.body is not None
    assert {f.name for f in route.body.fields} == {"amount", "currency"}
