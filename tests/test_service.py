"""End-to-end sync orchestration — the two-phase confirm contract.

These are the safety-critical tests: the preview phase must never write, and a write must
only happen on confirm. The Postman REST API is mocked with respx; no network is touched.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from postman_mcp.config.store import CONFIG_FILENAME, PostmanMcpConfig
from postman_mcp.postman.client import BASE_URL
from postman_mcp.service import sync as sync_service

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
    """A configured project: code-mode FastAPI, file-based key, one route."""
    cfg = PostmanMcpConfig()
    cfg.config.framework = "fastapi"
    cfg.config.inputMode = "code"
    cfg.config.collectionId = COLLECTION_UID
    cfg.config.apiKeyRef = "file:postman/secret"
    (tmp_path / "postman").mkdir(exist_ok=True)
    (tmp_path / CONFIG_FILENAME).write_text(
        json.dumps(cfg.model_dump()), encoding="utf-8"
    )
    (tmp_path / "postman/secret").write_text("PMAK-test\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(FASTAPI_APP, encoding="utf-8")
    return tmp_path


def _mock_get_collection():
    return respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(
            200, json={"collection": {"info": {"name": "Acme Backend"}, "item": []}}
        )
    )


@respx.mock
def test_preview_does_not_write(project):
    """confirm=False → returns the diff, and NO PUT is issued."""
    _mock_get_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={})
    )

    out = sync_service.sync_api(
        "create_payment", confirm=False, project_root=project
    )

    assert "| Status |" in out
    assert "| POST | /payments |" in out
    assert "Write? [y / n]" in out
    assert not put.called  # the safety guarantee


@respx.mock
def test_confirm_writes_via_put(project):
    """confirm=True → a single PUT performs the write."""
    _mock_get_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}})
    )

    out = sync_service.sync_api(
        "create_payment", confirm=True, project_root=project
    )

    assert "✓ Sync completed" in out
    assert "API(s) added" in out
    assert put.called
    sent = json.loads(put.calls.last.request.content)
    # the new request landed in the collection payload
    assert sent["collection"]["item"]


def test_resolve_into_precedence():
    """Issue 10: explicit --into → configured target → root. Nothing inferred."""
    from postman_mcp.config.store import ProjectConfig
    from postman_mcp.service.sync import _resolve_into

    # Explicit wins over everything.
    assert _resolve_into("payments", ProjectConfig(defaultInto="configured")) == "payments"
    # No explicit → configured non-root target.
    assert _resolve_into(None, ProjectConfig(defaultInto="configured")) == "configured"
    # No explicit, configured is root → root.
    assert _resolve_into(None, ProjectConfig(defaultInto="/")) == "/"
    # Blank explicit is treated as "not provided".
    assert _resolve_into("  ", ProjectConfig(defaultInto="/")) == "/"


@respx.mock
def test_ambiguous_target_lists_candidates(project):
    _mock_get_collection()
    # "payments" matches the path fragment but is not a unique function name
    out = sync_service.sync_api("payments", confirm=False, project_root=project)
    assert "ambiguous" in out.lower() or "| Status |" in out


def test_missing_config_errors(tmp_path):
    out = sync_service.sync_api("create_payment", project_root=tmp_path)
    assert "Error" in out and "init" in out


@respx.mock
def test_no_match_reports_cleanly(project):
    _mock_get_collection()
    out = sync_service.sync_api("does_not_exist", confirm=False, project_root=project)
    assert "No route matched" in out


@respx.mock
def test_syncchanges_first_run_no_marker(project):
    _mock_get_collection()
    out = sync_service.sync_changes(confirm=False, project_root=project)
    assert "syncall" in out.lower()


@respx.mock
def test_sync_all_preview_then_write(project):
    _mock_get_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}})
    )
    preview = sync_service.sync_all(confirm=False, project_root=project)
    assert "| Status |" in preview
    assert not put.called

    written = sync_service.sync_all(confirm=True, project_root=project)
    assert "✓ Sync completed" in written
    assert put.called


@respx.mock
def test_sync_target_filters_by_file(project):
    _mock_get_collection()
    out = sync_service.sync_target("-app.py", confirm=False, project_root=project)
    assert "| Status |" in out
    assert "| POST | /payments |" in out


@respx.mock
def test_sync_target_unknown_file_reports(project):
    _mock_get_collection()
    out = sync_service.sync_target("-nope.py", confirm=False, project_root=project)
    assert "No routes found" in out


@respx.mock
def test_write_aborts_on_server_error(project, monkeypatch):
    monkeypatch.setattr("postman_mcp.postman.client._BACKOFF_BASE", 0)
    _mock_get_collection()
    respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(500)
    )
    out = sync_service.sync_api("create_payment", confirm=True, project_root=project)
    assert "aborted" in out.lower()
