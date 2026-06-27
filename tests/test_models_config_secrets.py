"""Contracts, config round-trip, and secret handling."""

from __future__ import annotations

import json

import pytest

from postman_mcp.config.store import (
    CONFIG_FILENAME,
    ConfigError,
    PostmanMcpConfig,
    load_config,
    save_config,
)
from postman_mcp.models import RouteModel, normalize_path
from postman_mcp.secrets.manager import (
    SecretError,
    mask_if_secret,
    resolve_api_key,
    store_api_key,
)


# --- path normalization / identity ---------------------------------------

@pytest.mark.parametrize(
    "path,expected",
    [
        ("/users/:id", "/users/{param}"),
        ("/users/{id}", "/users/{param}"),
        ("/users/<id>", "/users/{param}"),
        ("/users/<int:id>", "/users/{param}"),
        ("users/{id}/", "/users/{param}"),
        ("/", "/"),
    ],
)
def test_normalize_path_unifies_param_styles(path, expected):
    assert normalize_path(path) == expected


def test_route_key_is_method_plus_normalized_path():
    a = RouteModel(method="post", path="/users/:id")
    b = RouteModel(method="POST", path="/users/{id}")
    assert a.key == b.key == "POST:/users/{param}"


# --- config round-trip, secret-free ---------------------------------------

def test_config_round_trip(tmp_path):
    cfg = PostmanMcpConfig()
    cfg.config.framework = "fastapi"
    cfg.config.collectionId = "col-123"
    cfg.mark_synced("a1b2c3d")

    save_config(cfg, tmp_path)
    loaded = load_config(tmp_path)

    assert loaded.config.framework == "fastapi"
    assert loaded.config.collectionId == "col-123"
    assert loaded.lastUpdate.commit == "a1b2c3d"
    assert loaded.lastUpdate.at  # timestamp set


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigError, match="postman-mcp init"):
        load_config(tmp_path)


def test_config_never_contains_raw_key(tmp_path):
    """The committable config must hold a reference, never the secret."""
    cfg = PostmanMcpConfig()
    cfg.config.apiKeyRef = "keychain:postman-mcp"
    save_config(cfg, tmp_path)

    raw = (tmp_path / CONFIG_FILENAME).read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["config"]["apiKeyRef"] == "keychain:postman-mcp"
    # A real Postman key looks like "PMAK-..."; it must never appear on disk.
    assert "PMAK-" not in raw


# --- secret resolver: file + env ----------------------------------------

def test_store_and_resolve_via_file(tmp_path):
    store_api_key("file:.postman-mcp.secret", "PMAK-abc123", tmp_path)
    secret_file = tmp_path / ".postman-mcp.secret"
    assert secret_file.exists()
    assert resolve_api_key("file:.postman-mcp.secret", tmp_path) == "PMAK-abc123"


def test_store_and_resolve_via_env(monkeypatch):
    monkeypatch.delenv("POSTMAN_API_KEY", raising=False)
    store_api_key("env:POSTMAN_API_KEY", "PMAK-env")
    assert resolve_api_key("env:POSTMAN_API_KEY") == "PMAK-env"


def test_resolve_missing_env_raises(monkeypatch):
    monkeypatch.delenv("POSTMAN_API_KEY", raising=False)
    with pytest.raises(SecretError):
        resolve_api_key("env:POSTMAN_API_KEY")


def test_resolve_unknown_scheme_raises():
    with pytest.raises(SecretError):
        resolve_api_key("smoke-signal:nope")


# --- env-var masking -----------------------------------------------------

@pytest.mark.parametrize("name", ["API_KEY", "auth_token", "client_secret", "db_password"])
def test_secret_names_are_masked(name):
    assert mask_if_secret(name) is True


@pytest.mark.parametrize("name", ["base_url", "timeout", "page_size"])
def test_non_secret_names_are_not_masked(name):
    assert mask_if_secret(name) is False
