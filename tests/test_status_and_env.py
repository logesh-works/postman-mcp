"""status (read-only drift) + createenv (environment generation) — PRD §10.2, §10.1, §16."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from postman_mcp.config.store import CONFIG_FILENAME, PostmanMcpConfig
from postman_mcp.postman.client import BASE_URL
from postman_mcp.service.environment import create_env
from postman_mcp.service.status import status_report

COLLECTION_UID = "col-123"

FASTAPI_APP = '''
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class PaymentRequest(BaseModel):
    amount: int


@app.post("/payments")
def create_payment(body: PaymentRequest):
    return {}
'''


@pytest.fixture
def project(tmp_path):
    cfg = PostmanMcpConfig()
    cfg.config.framework = "fastapi"
    cfg.config.inputMode = "code"
    cfg.config.collectionId = COLLECTION_UID
    cfg.config.apiKeyRef = "file:.postman-mcp.secret"
    (tmp_path / CONFIG_FILENAME).write_text(json.dumps(cfg.model_dump()), encoding="utf-8")
    (tmp_path / ".postman-mcp.secret").write_text("PMAK-test\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(FASTAPI_APP, encoding="utf-8")
    return tmp_path


def _mock_collection(items=None):
    return respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(
            200,
            json={"collection": {"info": {"name": "Acme"}, "item": items or []}},
        )
    )


@respx.mock
def test_status_reports_new_route_without_writing(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200)
    )
    out = status_report(project_root=project)
    assert "read-only" in out
    assert "POST /payments" in out
    assert not put.called


@respx.mock
def test_status_flags_drifted_route_as_deprecated(project):
    # Collection has a route that no longer exists in code.
    items = [{
        "name": "Legacy",
        "request": {"method": "DELETE", "url": {"raw": "{{base_url}}/legacy"}},
    }]
    _mock_collection(items)
    out = status_report(project_root=project)
    assert "[DEPRECATED]" in out
    assert "/legacy" in out


@respx.mock
def test_createenv_preview_masks_secrets(project):
    _mock_collection()
    out = create_env(name="Local", confirm=False, project_root=project)
    assert 'ENV PREVIEW' in out
    assert "base_url" in out
    # token is secret-like → masked
    assert "token" in out and "secret" in out
    assert "[ y / n ]".replace(" ", "") in out.replace(" ", "")


@respx.mock
def test_createenv_confirm_creates_environment(project):
    _mock_collection()
    post = respx.post(f"{BASE_URL}/environments").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-9"}})
    )
    out = create_env(name="Local", confirm=True, project_root=project)
    assert "✓ Created environment" in out
    assert post.called
