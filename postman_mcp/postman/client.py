"""REST client for ``https://api.getpostman.com``.

Auth: a single personal API key in the ``X-Api-Key`` header. The public Postman
API reads/writes a collection as one whole object — there is no per-request endpoint —
so writes are done by the merge layer: read → merge → ``PUT``.

API surface used:
| Validate key                 | GET  /me                       |
| List workspaces / collections| GET  /workspaces, /collections |
| Read collection              | GET  /collections/{uid}        |
| Write collection             | PUT  /collections/{uid}        |
| Create collection            | POST /collections              |
| Create / update environment  | POST /environments, PUT /environments/{uid} |
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

BASE_URL = "https://api.getpostman.com"
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds; retry with backoff on 5xx / 429


class PostmanError(Exception):
    """Generic Postman API failure (non-auth)."""


class PostmanAuthError(PostmanError):
    """Invalid / expired API key — stop, explain, never partial-write."""


class PostmanClient:
    """Thin synchronous wrapper over the Postman REST API.

    Retries transient 5xx / 429 with exponential backoff, then aborts cleanly with no
    partial collection write.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)
        self._headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    # -- lifecycle ------------------------------------------------------------------

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PostmanClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- low-level request with retry/backoff -----------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client.request(
                    method, path, headers=self._headers, **kwargs
                )
            except httpx.HTTPError as exc:  # network error
                last_exc = exc
                time.sleep(_BACKOFF_BASE * (2**attempt))
                continue

            if resp.status_code in (401, 403):
                raise PostmanAuthError(
                    "Postman API key is invalid or expired. Generate a new key at "
                    "Postman → Account Settings → API Keys and re-run "
                    "`postman-mcp init`."
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = PostmanError(
                    f"{method} {path} → {resp.status_code}"
                )
                time.sleep(_BACKOFF_BASE * (2**attempt))
                continue
            if resp.status_code >= 400:
                raise PostmanError(
                    f"{method} {path} → {resp.status_code}: {resp.text[:300]}"
                )
            if not resp.content:
                return {}
            return resp.json()

        raise PostmanError(
            f"{method} {path} failed after {_MAX_RETRIES} retries: {last_exc}"
        )

    # -- API surface -----------------------------------------------------

    def validate_key(self) -> dict[str, Any]:
        """``GET /me`` — validates the key."""
        return self._request("GET", "/me")

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._request("GET", "/workspaces").get("workspaces", [])

    def list_collections(
        self, workspace: Optional[str] = None
    ) -> list[dict[str, Any]]:
        params = {"workspace": workspace} if workspace else None
        return self._request("GET", "/collections", params=params).get(
            "collections", []
        )

    def get_collection(self, uid: str) -> dict[str, Any]:
        """``GET /collections/{uid}`` → full collection object."""
        return self._request("GET", f"/collections/{uid}").get("collection", {})

    def update_collection(self, uid: str, collection: dict[str, Any]) -> dict[str, Any]:
        """``PUT /collections/{uid}`` — the only write path."""
        return self._request(
            "PUT", f"/collections/{uid}", json={"collection": collection}
        )

    def create_collection(
        self, collection: dict[str, Any], workspace: Optional[str] = None
    ) -> dict[str, Any]:
        params = {"workspace": workspace} if workspace else None
        return self._request(
            "POST", "/collections", params=params, json={"collection": collection}
        ).get("collection", {})

    def create_environment(
        self, environment: dict[str, Any], workspace: Optional[str] = None
    ) -> dict[str, Any]:
        params = {"workspace": workspace} if workspace else None
        return self._request(
            "POST", "/environments", params=params, json={"environment": environment}
        ).get("environment", {})

    def update_environment(
        self, uid: str, environment: dict[str, Any]
    ) -> dict[str, Any]:
        return self._request(
            "PUT", f"/environments/{uid}", json={"environment": environment}
        ).get("environment", {})
