"""CLI terminal commands — version + the doctor setup-contract check."""

from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from postman_mcp import __version__
from postman_mcp import cli as cli_module
from postman_mcp.cli import app
from postman_mcp.config.store import CONFIG_FILENAME, PostmanMcpConfig
from postman_mcp.postman.client import BASE_URL
from postman_mcp.setup.installer import install_slash_commands
from postman_mcp.setup.registration import register_mcp_server

runner = CliRunner()
COLLECTION_UID = "col-123"


# --- init: workspace/collection pickers stick to the existing config on a re-run -----


class _FakeClient:
    def __init__(self, items):
        self._items = items

    def list_workspaces(self):
        return self._items

    def list_collections(self, workspace_id):
        return self._items


def _capture_default(monkeypatch):
    captured = {}

    def fake_prompt(text, default=None):
        captured["default"] = default
        return default

    monkeypatch.setattr(cli_module.typer, "prompt", fake_prompt)
    return captured


def test_pick_workspace_defaults_to_existing_on_rerun(monkeypatch):
    workspaces = [{"id": "ws-a", "name": "A"}, {"id": "ws-b", "name": "B"}]
    client = _FakeClient(workspaces)
    existing = PostmanMcpConfig()
    existing.config.workspace = "ws-b"
    captured = _capture_default(monkeypatch)

    result = cli_module._pick_workspace(client, existing)

    assert captured["default"] == "2"
    assert result == "ws-b"


def test_pick_workspace_defaults_to_first_when_no_existing(monkeypatch):
    client = _FakeClient([{"id": "ws-a", "name": "A"}])
    captured = _capture_default(monkeypatch)

    result = cli_module._pick_workspace(client, None)

    assert captured["default"] == "1"
    assert result == "ws-a"


def test_pick_collection_defaults_to_existing_on_rerun(monkeypatch, tmp_path):
    collections = [
        {"uid": "col-a", "name": "API Collection"},
        {"uid": "col-b", "name": "API Collection"},
    ]
    client = _FakeClient(collections)
    existing = PostmanMcpConfig()
    existing.config.collectionId = "col-b"
    captured = _capture_default(monkeypatch)

    result = cli_module._pick_collection(client, "ws-1", existing, tmp_path)

    # Must stick to the second "API Collection" (the one already configured), never
    # silently fall back to index 1 / create a duplicate.
    assert captured["default"] == "2"
    assert result == "col-b"


def test_pick_collection_defaults_to_first_when_no_existing(monkeypatch, tmp_path):
    client = _FakeClient([{"uid": "col-a", "name": "API Collection"}])
    captured = _capture_default(monkeypatch)

    result = cli_module._pick_collection(client, "ws-1", None, tmp_path)

    assert captured["default"] == "1"
    assert result == "col-a"


def test_version_prints_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_doctor_missing_config_fails_with_fix(tmp_path):
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "postman-mcp init" in result.stdout


def _configured_project(tmp_path):
    cfg = PostmanMcpConfig()
    cfg.config.collectionId = COLLECTION_UID
    cfg.config.apiKeyRef = "file:.postman-mcp.secret"
    (tmp_path / CONFIG_FILENAME).write_text(json.dumps(cfg.model_dump()), encoding="utf-8")
    (tmp_path / ".postman-mcp.secret").write_text("PMAK-test\n", encoding="utf-8")
    register_mcp_server(tmp_path)
    install_slash_commands(tmp_path)
    return tmp_path


@respx.mock
def test_doctor_all_checks_pass(tmp_path):
    project = _configured_project(tmp_path)
    respx.get(f"{BASE_URL}/me").mock(
        return_value=httpx.Response(200, json={"user": {"username": "jane"}})
    )
    respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {"info": {"name": "Acme"}}})
    )
    result = runner.invoke(app, ["doctor", "--path", str(project)])
    assert result.exit_code == 0
    assert "All setup-contract checks passed" in result.stdout


@respx.mock
def test_doctor_reports_bad_key(tmp_path):
    project = _configured_project(tmp_path)
    respx.get(f"{BASE_URL}/me").mock(return_value=httpx.Response(401))
    respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(401)
    )
    result = runner.invoke(app, ["doctor", "--path", str(project)])
    assert result.exit_code == 1
    assert "API key check failed" in result.stdout
