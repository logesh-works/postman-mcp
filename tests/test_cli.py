"""CLI terminal commands — version + the doctor setup-contract check."""

from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from postman_mcp import __version__
from postman_mcp.cli import app
from postman_mcp.config.store import CONFIG_FILENAME, PostmanMcpConfig
from postman_mcp.postman.client import BASE_URL
from postman_mcp.setup.installer import install_slash_commands
from postman_mcp.setup.registration import register_mcp_server

runner = CliRunner()
COLLECTION_UID = "col-123"


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
