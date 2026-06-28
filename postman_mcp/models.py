"""Core Pydantic contracts shared across every layer.

The most important contract is :class:`RouteModel` — the *normalized route model* that
both input paths (OpenAPI and code parsing) emit, so the engine and
everything downstream is identical regardless of source.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")


class InputSource(str, Enum):
    """Where a route model came from — surfaced in the diff as a label."""

    OPENAPI = "openapi"
    CODE = "code"


class ParamLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"


class FieldType(str, Enum):
    """Coarse field types used by the example generator."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    UNKNOWN = "unknown"


class Param(BaseModel):
    """A path / query / header parameter."""

    name: str
    location: ParamLocation
    type: FieldType = FieldType.STRING
    required: bool = False
    description: Optional[str] = None


class BodyField(BaseModel):
    """One field of a request/response body shape."""

    name: str
    type: FieldType = FieldType.UNKNOWN
    required: bool = True
    description: Optional[str] = None
    # For arrays/objects we keep the nested shape so examples stay realistic.
    items: Optional["BodyField"] = None
    fields: list["BodyField"] = Field(default_factory=list)


class BodyModel(BaseModel):
    """A typed request or response body."""

    name: Optional[str] = None
    fields: list[BodyField] = Field(default_factory=list)
    # True when the source could not produce a real type (Express, untyped) — the diff
    # flags these "lower confidence".
    low_confidence: bool = False


class ResponseModel(BaseModel):
    """One declared response, keyed by status code."""

    status: int
    description: Optional[str] = None
    body: Optional[BodyModel] = None


class RouteModel(BaseModel):
    """The normalized route model — the single contract feeding the engine.

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
        """Identity used to match against the live collection."""
        return f"{self.method.upper()}:{normalize_path(self.path)}"


# --- path normalization ---------------------------------------------------

import re

_BRACE = re.compile(r"\{[^}]+\}")
_COLON = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_ANGLE = re.compile(r"<(?:[^:>]+:)?([^>]+)>")


def normalize_path(path: str) -> str:
    """Normalize ``/users/:id`` ≡ ``/users/{id}`` ≡ ``/users/<id>`` → ``/users/{id}``.

    A route is keyed by ``METHOD + normalized path``.
    """
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    # angle first: ``<int:id>`` carries a colon the :param rule must not match
    p = _ANGLE.sub(lambda m: "{" + m.group(1) + "}", p)
    p = _COLON.sub(lambda m: "{" + m.group(1) + "}", p)
    # collapse any {anything} placeholder to {param} so differing names still match
    p = _BRACE.sub("{param}", p)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


# --- diff contracts -------------------------------------------------------


class ChangeType(str, Enum):
    NEW = "new"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"  # soft delete
    UNCHANGED = "unchanged"


class RequestDiff(BaseModel):
    """A single request's planned change, rendered in the diff preview."""

    change: ChangeType
    method: str
    path: str
    into: str
    source: InputSource
    lines: list[str] = Field(default_factory=list)  # rendered "+ Body ..." lines
    preserved: list[str] = Field(default_factory=list)  # human-owned fields kept
    low_confidence: bool = False
    # Table columns (diff/render.py renders these as the default preview format).
    auth: str = "—"
    body_name: str = "—"
    response_name: str = "—"


class SyncPlan(BaseModel):
    """The full plan for a sync operation — the diff is rendered from this."""

    collection_id: str
    collection_name: Optional[str] = None
    is_default_collection: bool = True
    diffs: list[RequestDiff] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)  # parse failures

    @property
    def has_changes(self) -> bool:
        return any(d.change != ChangeType.UNCHANGED for d in self.diffs)


BodyField.model_rebuild()
