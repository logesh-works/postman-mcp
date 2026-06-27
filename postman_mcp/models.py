"""Core Pydantic contracts shared across every layer.

The most important contract is :class:`RouteModel` — the *normalized route model* that
both input paths (OpenAPI §9.3 and code parsing §9.4) emit, so the engine (§8) and
everything downstream is identical regardless of source (PRD §9.1).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


class InputSource(str, Enum):
    """Where a route model came from — surfaced in the diff as a label (PRD §9.5, §13)."""

    OPENAPI = "openapi"
    CODE = "code"


class ParamLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"


class FieldType(str, Enum):
    """Coarse field types used by the example generator (PRD §8.3)."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    UNKNOWN = "unknown"


class Param(BaseModel):
    """A path / query / header parameter (PRD §8 step 2)."""

    name: str
    location: ParamLocation
    type: FieldType = FieldType.STRING
    required: bool = False
    description: Optional[str] = None


class BodyField(BaseModel):
    """One field of a request/response body shape (PRD §8 step 3/5)."""

    name: str
    type: FieldType = FieldType.UNKNOWN
    required: bool = True
    description: Optional[str] = None
    # For arrays/objects we keep the nested shape so examples stay realistic.
    items: Optional["BodyField"] = None
    fields: list["BodyField"] = Field(default_factory=list)


class BodyModel(BaseModel):
    """A typed request or response body (PRD §8 step 3/5)."""

    name: Optional[str] = None
    fields: list[BodyField] = Field(default_factory=list)
    # True when the source could not produce a real type (Express, untyped) — the diff
    # flags these "lower confidence" (PRD §9.4, §18).
    low_confidence: bool = False


class ResponseModel(BaseModel):
    """One declared response, keyed by status code (PRD §8 step 5)."""

    status: int
    description: Optional[str] = None
    body: Optional[BodyModel] = None


class RouteModel(BaseModel):
    """The normalized route model — the single contract feeding the engine (PRD §9.1).

    ``{ method, path, pathParams, queryParams, headers, bodyType,
        responseTypes, authRequired, docstring, codeRef }``
    """

    method: str
    path: str
    path_params: list[Param] = Field(default_factory=list)
    query_params: list[Param] = Field(default_factory=list)
    headers: list[Param] = Field(default_factory=list)
    body: Optional[BodyModel] = None
    responses: list[ResponseModel] = Field(default_factory=list)
    auth_required: bool = False
    docstring: Optional[str] = None
    code_ref: Optional[str] = None
    source: InputSource = InputSource.OPENAPI

    @property
    def key(self) -> str:
        """Identity used to match against the live collection (PRD §15)."""
        return f"{self.method.upper()}:{normalize_path(self.path)}"


# --- path normalization (PRD §15) ---------------------------------------------------

import re

_BRACE = re.compile(r"\{[^}]+\}")
_COLON = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_ANGLE = re.compile(r"<(?:[^:>]+:)?([^>]+)>")


def normalize_path(path: str) -> str:
    """Normalize ``/users/:id`` ≡ ``/users/{id}`` ≡ ``/users/<id>`` → ``/users/{id}``.

    A route is keyed by ``METHOD + normalized path`` (PRD §15).
    """
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    # angle first: ``<int:id>`` carries a colon the :param rule must not match (PRD §15)
    p = _ANGLE.sub(lambda m: "{" + m.group(1) + "}", p)
    p = _COLON.sub(lambda m: "{" + m.group(1) + "}", p)
    # collapse any {anything} placeholder to {param} so differing names still match
    p = _BRACE.sub("{param}", p)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


# --- diff contracts (PRD §13) -------------------------------------------------------


class ChangeType(str, Enum):
    NEW = "new"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"  # soft delete (PRD §15, §17)
    UNCHANGED = "unchanged"


class RequestDiff(BaseModel):
    """A single request's planned change, rendered in the diff preview (PRD §13)."""

    change: ChangeType
    method: str
    path: str
    into: str
    source: InputSource
    lines: list[str] = Field(default_factory=list)  # rendered "+ Body ..." lines
    preserved: list[str] = Field(default_factory=list)  # human-owned fields kept (§15)
    low_confidence: bool = False


class SyncPlan(BaseModel):
    """The full plan for a sync operation — the diff is rendered from this (PRD §13)."""

    collection_id: str
    collection_name: Optional[str] = None
    is_default_collection: bool = True
    diffs: list[RequestDiff] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)  # parse failures (§18)

    @property
    def has_changes(self) -> bool:
        return any(d.change != ChangeType.UNCHANGED for d in self.diffs)


BodyField.model_rebuild()
