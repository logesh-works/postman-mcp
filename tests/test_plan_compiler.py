"""The Plan Compiler — verified APIM → executable, hash-bound plan."""

from __future__ import annotations

from postman_mcp.config.store import ProjectConfig
from postman_mcp.plan.compiler import collection_hash, compile_plan, compute_plan_id, load_plan, plan_is_expired
from postman_mcp.verify.pipeline import run_pipeline
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


@app.get("/health")
def health():
    return {"ok": True}
'''


def _project(tmp_path):
    (tmp_path / "app.py").write_text(FASTAPI_APP, encoding="utf-8")
    return tmp_path


def _model_and_report(project):
    ws = build_witness_set(project, ProjectConfig(framework="fastapi", inputMode="code"))
    apim = witness_to_apim(ws, project_root=project)
    report = run_pipeline(apim, project)
    return apim, report


def test_compile_plan_produces_entries_for_all_syncable_endpoints(tmp_path):
    project = _project(tmp_path)
    apim, report = _model_and_report(project)
    collection = {"info": {"name": "Test"}, "item": []}
    doc = compile_plan(
        apim, report, collection=collection, collection_id="col-1",
        into="/", project_root=project,
    )
    assert len(doc.entries) == 2
    assert all(e.gate_action in ("auto", "flag") for e in doc.entries)
    assert not doc.rejected
    assert not doc.blocked_uids


def test_plan_id_is_deterministic_given_same_inputs(tmp_path):
    project = _project(tmp_path)
    apim, report = _model_and_report(project)
    collection = {"info": {"name": "Test"}, "item": []}
    doc1 = compile_plan(apim, report, collection=collection, collection_id="col-1", into="/", project_root=project)
    doc2 = compile_plan(apim, report, collection=collection, collection_id="col-1", into="/", project_root=project)
    assert doc1.plan_id == doc2.plan_id


def test_plan_id_changes_when_collection_changes(tmp_path):
    project = _project(tmp_path)
    apim, report = _model_and_report(project)
    empty = {"info": {"name": "Test"}, "item": []}
    nonempty = {"info": {"name": "Test"}, "item": [{"name": "x"}]}
    assert collection_hash(empty) != collection_hash(nonempty)
    id1 = compute_plan_id(report.model_id, collection_hash(empty), "all", "/")
    id2 = compute_plan_id(report.model_id, collection_hash(nonempty), "all", "/")
    assert id1 != id2


def test_plan_persists_and_reloads(tmp_path):
    project = _project(tmp_path)
    apim, report = _model_and_report(project)
    collection = {"info": {"name": "Test"}, "item": []}
    doc = compile_plan(apim, report, collection=collection, collection_id="col-1", into="/", project_root=project)
    reloaded = load_plan(doc.plan_id, project)
    assert reloaded.plan_id == doc.plan_id
    assert len(reloaded.entries) == len(doc.entries)


def test_plan_scope_uids_narrows_entries(tmp_path):
    project = _project(tmp_path)
    apim, report = _model_and_report(project)
    collection = {"info": {"name": "Test"}, "item": []}
    one_uid = {apim.endpoints[0].uid}
    doc = compile_plan(
        apim, report, collection=collection, collection_id="col-1",
        scope_uids=one_uid, into="/", project_root=project,
    )
    assert len(doc.entries) == 1
    assert doc.entries[0].uid in one_uid


def test_plan_not_expired_immediately(tmp_path):
    project = _project(tmp_path)
    apim, report = _model_and_report(project)
    collection = {"info": {"name": "Test"}, "item": []}
    doc = compile_plan(apim, report, collection=collection, collection_id="col-1", into="/", project_root=project)
    assert not plan_is_expired(doc, ttl_hours=24)
    assert plan_is_expired(doc, ttl_hours=-1)  # forced-expired sanity check
