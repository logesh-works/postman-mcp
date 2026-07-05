"""APIM ``Endpoint`` → ``RouteModel`` — the engine's input contract is untouched.

This is a lossy-but-sufficient projection: the engine only ever needed method, path,
params, a body/response shape, and an auth flag to build a Postman item — exactly what
an :class:`~postman_mcp.contract.schema.Endpoint` carries once verification has run.
Provenance/confidence stay in the verification report, not in ``RouteModel``, so
``engine/builder.py`` and ``postman/merge.py`` need no changes at all.
"""

from __future__ import annotations

from postman_mcp.contract.schema import Endpoint, ParamValue, SchemaNode, Traced
from postman_mcp.models import (
    BodyField,
    BodyModel,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)

_LOCATION = {
    "path": ParamLocation.PATH,
    "query": ParamLocation.QUERY,
    "header": ParamLocation.HEADER,
}


def _param(traced: Traced) -> Param:
    v: ParamValue = traced.value
    return Param(
        name=v.name,
        location=_LOCATION[v.location],
        type=v.type,
        required=v.required,
        description=v.description,
    )


def _schema_node_to_body_field(node: SchemaNode) -> BodyField:
    return BodyField(
        name=node.field_name or node.name or "",
        type=node.type,
        required=node.required,
        description=node.description,
        items=_schema_node_to_body_field(node.items) if node.items else None,
        fields=[_schema_node_to_body_field(f) for f in node.fields],
    )


def _schema_node_to_body_model(node: SchemaNode, *, low_confidence: bool = False) -> BodyModel:
    return BodyModel(
        name=node.name,
        fields=[_schema_node_to_body_field(f) for f in node.fields],
        low_confidence=low_confidence,
    )


def endpoint_to_route_model(endpoint: Endpoint) -> RouteModel:
    """Project one verified APIM endpoint into the engine's ``RouteModel`` contract."""
    body = None
    if endpoint.request_body is not None:
        low_conf = endpoint.request_body.confidence < 0.75
        body = _schema_node_to_body_model(endpoint.request_body.value.schema_, low_confidence=low_conf)

    responses = []
    for traced_resp in endpoint.responses:
        r = traced_resp.value
        resp_body = _schema_node_to_body_model(r.schema_) if r.schema_ is not None else None
        responses.append(ResponseModel(status=r.status, description=r.description, body=resp_body))

    docstring = None
    if endpoint.description is not None:
        docstring = endpoint.description.value
    elif endpoint.summary is not None:
        docstring = endpoint.summary.value

    code_ref = None
    if endpoint.identity_evidence:
        first = endpoint.identity_evidence[0]
        code_ref = f"{first.file}::{first.symbol}" if first.symbol else first.file

    source = InputSource.OPENAPI if any(
        e.extraction_method.value == "openapi_verified" for e in endpoint.identity_evidence
    ) else InputSource.CODE

    return RouteModel(
        method=endpoint.method.upper(),
        path=endpoint.path,
        path_params=[_param(p) for p in endpoint.path_params],
        query_params=[_param(p) for p in endpoint.query_params],
        headers=[_param(p) for p in endpoint.headers],
        body=body,
        responses=responses,
        auth_required=endpoint.auth.value.required,
        docstring=docstring,
        code_ref=code_ref,
        source=source,
    )
