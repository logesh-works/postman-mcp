"""End-to-end submitted-model flow: get_contract → submit_model → plan → apply.

Mirrors ``test_service.py``'s conventions: the Postman API is mocked with respx, no
network is touched, and the safety-critical assertion is that nothing writes without
an explicit ``apply(..., confirm=True)`` against a plan whose collection hash still
matches what's live.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from postman_mcp.config.store import CONFIG_FILENAME, PostmanMcpConfig
from postman_mcp.postman.client import BASE_URL
from postman_mcp.service import aiplan

COLLECTION_UID = "col-123"

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
    cfg = PostmanMcpConfig()
    cfg.config.framework = "fastapi"
    cfg.config.inputMode = "code"
    cfg.config.collectionId = COLLECTION_UID
    cfg.config.apiKeyRef = "file:postman/secret"
    (tmp_path / "postman").mkdir(exist_ok=True)
    (tmp_path / CONFIG_FILENAME).write_text(json.dumps(cfg.model_dump()), encoding="utf-8")
    (tmp_path / "postman/secret").write_text("PMAK-test\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(FASTAPI_APP, encoding="utf-8")
    return tmp_path


def _mock_get_collection(collection=None):
    body = collection or {"info": {"name": "Acme Backend"}, "item": []}
    return respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": body})
    )


def test_get_contract_tool_is_provider_agnostic():
    contract = aiplan.get_contract_tool()
    assert "apim_schema" in contract and "playbook" in contract


@respx.mock
def test_plan_without_model_id_uses_witness_fallback(project):
    _mock_get_collection()
    preview = aiplan.plan(project_root=project)
    assert "POST" in preview and "/payments" in preview
    assert "plan_id:" in preview


@respx.mock
def test_plan_without_model_id_uses_graph_witness_on_engine_v3(project):
    """engine: "v3" routes the fallback producer through the graph witness instead of
    the parser witness (Phase 4). Route identity still resolves (grounded decorator +
    HTTP verb), but the honest fidelity gap — no schema extraction — is real: assert
    it directly at the APIM level rather than guessing at a rendered table string."""
    cfg = json.loads((project / CONFIG_FILENAME).read_text())
    cfg["config"]["engine"] = "v3"
    (project / CONFIG_FILENAME).write_text(json.dumps(cfg), encoding="utf-8")

    _mock_get_collection()
    preview = aiplan.plan(project_root=project)
    assert "POST" in preview and "/payments" in preview

    from postman_mcp.verify.graph_witness import build_graph_witness
    from postman_mcp.witness.engine import witness_to_apim

    apim = witness_to_apim(build_graph_witness(project), project_root=project)
    assert apim.endpoints[0].request_body is None  # documented gap: no schema extraction


@respx.mock
def test_plan_and_apply_writes_via_put(project):
    _mock_get_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}})
    )
    preview = aiplan.plan(project_root=project)
    assert not put.called
    plan_id = preview.split("plan_id: ")[1].splitlines()[0].strip()

    result = aiplan.apply(plan_id, confirm=True, project_root=project)
    assert "✓" in result
    assert put.called


@respx.mock
def test_dry_run_plan_does_not_persist(project):
    _mock_get_collection()
    preview = aiplan.plan(dry_run=True, project_root=project)
    assert "dry run" in preview
    plan_id = preview.split("plan_id: ")[1].split(" ")[0].strip()
    with pytest.raises(FileNotFoundError):
        from postman_mcp.plan.compiler import load_plan
        load_plan(plan_id, project)


@respx.mock
def test_apply_aborts_when_collection_changed_since_plan(project):
    empty = {"info": {"name": "Acme Backend"}, "item": []}
    changed = {"info": {"name": "Acme Backend"}, "item": [{"name": "drift",
               "request": {"method": "GET", "url": "{{base_url}}/drift"}}]}
    respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        side_effect=[
            httpx.Response(200, json={"collection": empty}),
            httpx.Response(200, json={"collection": changed}),
        ]
    )
    preview = aiplan.plan(project_root=project)
    plan_id = preview.split("plan_id: ")[1].splitlines()[0].strip()

    result = aiplan.apply(plan_id, confirm=True, project_root=project)
    assert "re-plan" in result.lower()


@respx.mock
def test_apply_rejects_unknown_approve_uid(project):
    _mock_get_collection()
    preview = aiplan.plan(project_root=project)
    plan_id = preview.split("plan_id: ")[1].splitlines()[0].strip()

    result = aiplan.apply(plan_id, approve=["not-a-real-uid"], confirm=True, project_root=project)
    assert "Error" in result and "not-a-real-uid" in result


@respx.mock
def test_readonly_write_protection_blocks_apply(project):
    cfg = PostmanMcpConfig.model_validate(json.loads((project / CONFIG_FILENAME).read_text()))
    cfg.config.writeProtection = "readonly"
    (project / CONFIG_FILENAME).write_text(json.dumps(cfg.model_dump()), encoding="utf-8")

    _mock_get_collection()
    result = aiplan.apply("nonexistent-plan-id", confirm=True, project_root=project)
    assert "readonly" in result.lower()


@respx.mock
def test_snapshot_and_rollback_round_trip(project):
    _mock_get_collection()
    snap_result = aiplan.snapshot(label="before", project_root=project)
    assert "✓" in snap_result
    snap_id = snap_result.split(": ")[1].strip()

    _mock_get_collection()
    preview = aiplan.rollback(snap_id, confirm=False, project_root=project)
    assert "No difference" in preview

    _mock_get_collection()
    respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    result = aiplan.rollback(snap_id, confirm=True, project_root=project)
    assert "Restored" in result


@respx.mock
def test_audit_log_records_the_flow(project):
    _mock_get_collection()
    aiplan.plan(project_root=project)
    log = aiplan.audit_log(project_root=project)
    assert "plan" in log
