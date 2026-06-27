"""Setup: slash-command install + MCP registration + gitignore."""

from __future__ import annotations

import json

from postman_mcp.setup.installer import (
    COMMAND_NAMES,
    install_slash_commands,
    slash_commands_present,
)
from postman_mcp.setup.registration import (
    SERVER_NAME,
    ensure_gitignore,
    is_server_registered,
    register_mcp_server,
)


def test_install_slash_commands(tmp_path):
    assert slash_commands_present(tmp_path) is False
    installed = install_slash_commands(tmp_path)
    assert len(installed) == len(COMMAND_NAMES)
    assert slash_commands_present(tmp_path) is True
    # the postman: namespace comes from the folder
    target = tmp_path / ".claude" / "commands" / "postman"
    assert (target / "syncapi.md").exists()


def test_install_is_idempotent(tmp_path):
    install_slash_commands(tmp_path)
    install_slash_commands(tmp_path)  # re-copy on upgrade — no error, still present
    assert slash_commands_present(tmp_path) is True


def test_register_mcp_server_writes_entry(tmp_path):
    assert is_server_registered(tmp_path) is False
    path = register_mcp_server(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["mcpServers"][SERVER_NAME]
    assert entry["command"] == "postman-mcp"
    assert entry["args"] == ["serve"]
    assert is_server_registered(tmp_path) is True


def test_register_preserves_existing_servers(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "x"}}}), encoding="utf-8"
    )
    register_mcp_server(tmp_path)
    data = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert "other" in data["mcpServers"]
    assert SERVER_NAME in data["mcpServers"]


def test_register_recovers_from_corrupt_json(tmp_path):
    (tmp_path / ".mcp.json").write_text("{not json", encoding="utf-8")
    register_mcp_server(tmp_path)
    assert is_server_registered(tmp_path) is True


def test_ensure_gitignore_adds_secret_once(tmp_path):
    ensure_gitignore(tmp_path)
    ensure_gitignore(tmp_path)  # idempotent
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert content.count(".postman-mcp.secret") == 1
