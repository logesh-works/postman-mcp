"""Postman REST client — auth, retry/backoff, and the API surface (PRD §6, §18)."""

from __future__ import annotations

import httpx
import pytest
import respx

from postman_mcp.postman.client import (
    BASE_URL,
    PostmanAuthError,
    PostmanClient,
    PostmanError,
)


@respx.mock
def test_validate_key_calls_me():
    route = respx.get(f"{BASE_URL}/me").mock(
        return_value=httpx.Response(200, json={"user": {"id": 1}})
    )
    with PostmanClient("PMAK-x") as client:
        assert client.validate_key() == {"user": {"id": 1}}
    assert route.called
    # the key travels in X-Api-Key, never in the URL
    assert route.calls.last.request.headers["X-Api-Key"] == "PMAK-x"


@respx.mock
def test_401_raises_auth_error():
    respx.get(f"{BASE_URL}/me").mock(return_value=httpx.Response(401))
    with PostmanClient("bad") as client:
        with pytest.raises(PostmanAuthError):
            client.validate_key()


@respx.mock
def test_retries_on_500_then_succeeds(monkeypatch):
    monkeypatch.setattr("postman_mcp.postman.client._BACKOFF_BASE", 0)  # no real sleep
    route = respx.get(f"{BASE_URL}/collections/c1").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"collection": {"info": {"name": "Acme"}}}),
        ]
    )
    with PostmanClient("PMAK-x") as client:
        col = client.get_collection("c1")
    assert col == {"info": {"name": "Acme"}}
    assert route.call_count == 2


@respx.mock
def test_persistent_500_aborts_cleanly(monkeypatch):
    monkeypatch.setattr("postman_mcp.postman.client._BACKOFF_BASE", 0)
    respx.put(f"{BASE_URL}/collections/c1").mock(return_value=httpx.Response(503))
    with PostmanClient("PMAK-x") as client:
        with pytest.raises(PostmanError):
            client.update_collection("c1", {"info": {"name": "Acme"}})


@respx.mock
def test_list_workspaces_and_collections():
    respx.get(f"{BASE_URL}/workspaces").mock(
        return_value=httpx.Response(200, json={"workspaces": [{"id": "w1"}]})
    )
    respx.get(f"{BASE_URL}/collections").mock(
        return_value=httpx.Response(200, json={"collections": [{"uid": "c1"}]})
    )
    with PostmanClient("PMAK-x") as client:
        assert client.list_workspaces() == [{"id": "w1"}]
        assert client.list_collections("w1") == [{"uid": "c1"}]
