"""Schemas for the LLM-authored sync artifacts under ``postman/sync/``.

The LLM-driven flow (see ``docs/architecture/v3-proposal.md`` and the collection-
authoring playbook) has any LLM write three files; the MCP reads and verifies them:

- ``collection.json`` — a Postman Collection v2.1 the LLM authors directly. Not modeled
  here in full (Postman owns that schema); ``filesync`` validates the shape it depends on.
- ``metadata.json`` — the **verification sidecar**: for each endpoint, the citations the
  MCP re-reads (never trusting the claim) and the DTO fields the LLM claims, so field
  grounding (``index/fields.py``) can confirm them against real code.
- ``sync.config.json`` — scope/target/generator info the LLM echoes; cross-checked
  against ``postman/config.json``.

``Citation`` deliberately mirrors ``contract/schema.py::Evidence`` (same fields, same
``snippet_sha256`` hashing spec via ``verify/evidence.py::hash_snippet``) so the exact
same auditor re-reads both an APIM submission and a file-sync submission.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """One cited source span — re-read and re-hashed by ``verify/evidence.py``."""

    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    symbol: Optional[str] = None
    snippet_sha256: str = ""
    quote: str = Field(default="", max_length=200)


class DtoClaim(BaseModel):
    """A claimed request/response body: the DTO class cited + the field names on it."""

    dto: Optional[Citation] = None          # the class declaration span
    fields: list[str] = Field(default_factory=list)  # claimed attribute names


class AuthClaim(BaseModel):
    """Where auth is enforced for this endpoint — a guard/middleware/decorator citation.

    Optional: an endpoint with no ``auth`` claim simply shows as auth-unverified in the
    diff (informational, never excluded). One that IS given and fails the hash audit is
    treated like any other citation failure — the endpoint is excluded from the write.
    """

    cited: Optional[Citation] = None
    required: bool = True
    scheme: str = "bearer"


class EndpointMeta(BaseModel):
    """Verification metadata for one request item in ``collection.json``.

    ``key`` is ``METHOD:/normalized-path`` — identical to
    ``postman/merge.py::item_key`` — so the MCP joins this metadata to the matching
    request item in the collection without guessing.
    """

    key: str
    citations: list[Citation] = Field(default_factory=list)  # existence/path evidence
    body: Optional[DtoClaim] = None
    responses: list[DtoClaim] = Field(default_factory=list)
    auth: Optional[AuthClaim] = None


class SyncMetadata(BaseModel):
    """``metadata.json`` root."""

    endpoints: list[EndpointMeta] = Field(default_factory=list)

    def by_key(self) -> dict[str, EndpointMeta]:
        return {e.key: e for e in self.endpoints}


class SyncConfigFile(BaseModel):
    """``sync.config.json`` — informational scope/generator echo, all optional."""

    scope: str = "all"                       # "all" | "api" | "file" | "changes" | ...
    target: Optional[str] = None             # the argument for scoped syncs
    into: Optional[str] = None               # optional folder prefix
    collection_id: Optional[str] = None      # must match postman/config.json if present
    generator: Optional[str] = None          # the LLM/model that produced the artifacts
    notes: list[str] = Field(default_factory=list)


def export_metadata_schema() -> dict[str, Any]:
    return SyncMetadata.model_json_schema()


def export_sync_config_schema() -> dict[str, Any]:
    return SyncConfigFile.model_json_schema()
