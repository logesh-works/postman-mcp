"""Path A — map an OpenAPI 3.x document into route models.

This path needs no framework-specific code: one mapper covers every framework that emits
a valid OpenAPI 3.x document (FastAPI, NestJS+swagger, DRF+spectacular). ``$ref``s are
resolved against ``components.schemas`` with a small hand-rolled resolver.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Optional

import yaml

from postman_mcp.models import (
    BodyField,
    BodyModel,
    FieldType,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)

_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


class OpenApiError(Exception):
    """Spec could not be loaded/parsed — caller falls back to code parsing."""


# --- loading ------------------------------------------------------------------------


def load_spec(source: str, *, timeout: float = 5.0) -> dict[str, Any]:
    """Load a spec from a URL or file path (JSON or YAML). Raises :class:`OpenApiError`."""
    try:
        if source.startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8")
        else:
            raw = Path(source).read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise OpenApiError(f"Could not read OpenAPI source {source!r}: {exc}") from exc

    try:
        if source.endswith((".yaml", ".yml")):
            return yaml.safe_load(raw)
        return json.loads(raw)
    except (json.JSONDecodeError, yaml.YAMLError):
        # Content-type can differ from extension (e.g. a URL serving YAML); try both.
        try:
            return yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise OpenApiError(f"OpenAPI source {source!r} is not valid JSON/YAML") from exc


# --- $ref resolution + schema → body model -----------------------------------------


def _resolve_ref(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve a local ``#/components/schemas/X`` ref."""
    if not ref.startswith("#/"):
        return {}
    node: Any = spec
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            return {}
        node = node[part]
    return node if isinstance(node, dict) else {}


_TYPE_MAP = {
    "string": FieldType.STRING,
    "integer": FieldType.INTEGER,
    "number": FieldType.NUMBER,
    "boolean": FieldType.BOOLEAN,
    "array": FieldType.ARRAY,
    "object": FieldType.OBJECT,
}


def _field_type(schema: dict[str, Any]) -> FieldType:
    return _TYPE_MAP.get(schema.get("type", ""), FieldType.UNKNOWN)


def _schema_to_body(
    schema: dict[str, Any],
    spec: dict[str, Any],
    *,
    name: Optional[str] = None,
    _depth: int = 0,
    _seen: Optional[set[str]] = None,
) -> BodyModel:
    """Convert a JSON Schema object into a flat-ish BodyModel."""
    seen = _seen or set()
    schema = _deref(schema, spec, seen)
    fields: list[BodyField] = []
    required = set(schema.get("required", []))
    for prop_name, prop_schema in (schema.get("properties") or {}).items():
        fields.append(
            _schema_to_field(
                prop_name, prop_schema, spec, prop_name in required, _depth, seen
            )
        )
    return BodyModel(name=name or schema.get("title"), fields=fields)


def _deref(
    schema: dict[str, Any], spec: dict[str, Any], seen: set[str]
) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref:
        if ref in seen:  # cycle guard
            return {}
        seen.add(ref)
        # recurse so a resolved target that itself uses allOf/$ref is handled
        return _deref(_resolve_ref(ref, spec), spec, seen)
    # allOf merge (common in generated specs)
    if "allOf" in schema:
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for sub in schema["allOf"]:
            sub = _deref(sub, spec, seen)
            merged["properties"].update(sub.get("properties", {}))
            merged["required"].extend(sub.get("required", []))
        return merged
    return schema


def _schema_to_field(
    name: str,
    schema: dict[str, Any],
    spec: dict[str, Any],
    required: bool,
    depth: int,
    seen: set[str],
) -> BodyField:
    schema = _deref(schema, spec, set(seen))
    ftype = _field_type(schema)
    field = BodyField(
        name=name,
        type=ftype,
        required=required,
        description=schema.get("description"),
    )
    if ftype is FieldType.OBJECT and depth < 4:
        nested = _schema_to_body(schema, spec, _depth=depth + 1, _seen=set(seen))
        field.fields = nested.fields
    elif ftype is FieldType.ARRAY and depth < 4:
        items = _deref(schema.get("items", {}), spec, set(seen))
        field.items = _schema_to_field(
            "item", items, spec, True, depth + 1, set(seen)
        )
    return field


# --- the mapper ---------------------------------------------------------------------


def routes_from_spec(spec: dict[str, Any]) -> list[RouteModel]:
    """Map ``paths.{path}.{method}`` into normalized route models."""
    routes: list[RouteModel] = []
    security_schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    global_security = spec.get("security") or []

    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        shared_params = path_item.get("parameters", [])
        for method in _METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            routes.append(
                _operation_to_route(
                    method.upper(),
                    path,
                    op,
                    spec,
                    shared_params,
                    security_schemes,
                    global_security,
                )
            )
    return routes


def _operation_to_route(
    method: str,
    path: str,
    op: dict[str, Any],
    spec: dict[str, Any],
    shared_params: list[dict[str, Any]],
    security_schemes: dict[str, Any],
    global_security: list[dict[str, Any]],
) -> RouteModel:
    path_params: list[Param] = []
    query_params: list[Param] = []
    headers: list[Param] = []

    for raw in [*shared_params, *op.get("parameters", [])]:
        raw = _deref(raw, spec, set())
        loc = raw.get("in")
        param = Param(
            name=raw.get("name", ""),
            location=ParamLocation(loc) if loc in {"path", "query", "header"} else ParamLocation.QUERY,
            type=_field_type(raw.get("schema", {})),
            required=raw.get("required", loc == "path"),
            description=raw.get("description"),
        )
        if loc == "path":
            path_params.append(param)
        elif loc == "header":
            headers.append(param)
        else:
            query_params.append(param)

    body: Optional[BodyModel] = None
    request_body = op.get("requestBody")
    if isinstance(request_body, dict):
        content = request_body.get("content", {})
        schema = _pick_json_schema(content)
        if schema is not None:
            body = _schema_to_body(schema, spec, name="RequestBody")

    responses: list[ResponseModel] = []
    for code, resp in (op.get("responses") or {}).items():
        if not isinstance(resp, dict):
            continue
        try:
            status = int(code)
        except ValueError:
            continue  # skip "default"
        schema = _pick_json_schema(resp.get("content", {}))
        responses.append(
            ResponseModel(
                status=status,
                description=resp.get("description"),
                body=_schema_to_body(schema, spec, name=f"Response{status}")
                if schema is not None
                else None,
            )
        )

    op_security = op.get("security", global_security)
    auth_required = bool(op_security) and bool(security_schemes)

    return RouteModel(
        method=method,
        path=path,
        path_params=path_params,
        query_params=query_params,
        headers=headers,
        body=body,
        responses=responses,
        auth_required=auth_required,
        docstring=op.get("summary") or op.get("description"),
        code_ref=op.get("operationId"),
        source=InputSource.OPENAPI,
    )


def _pick_json_schema(content: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Prefer ``application/json``; fall back to the first content type."""
    if not content:
        return None
    if "application/json" in content:
        return content["application/json"].get("schema")
    for media in content.values():
        if isinstance(media, dict) and "schema" in media:
            return media["schema"]
    return None
