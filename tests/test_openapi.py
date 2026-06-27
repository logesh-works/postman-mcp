"""Path A — OpenAPI 3.x → route models (PRD §9.3)."""

from __future__ import annotations

import json

import pytest

from postman_mcp.input.openapi import OpenApiError, load_spec, routes_from_spec
from postman_mcp.models import FieldType, InputSource


def test_routes_from_spec_maps_both_paths(openapi_spec):
    routes = {r.key: r for r in routes_from_spec(openapi_spec)}
    assert "POST:/payments" in routes
    assert "GET:/payments/{param}" in routes


def test_post_route_resolves_ref_and_allof(openapi_spec):
    routes = {r.method: r for r in routes_from_spec(openapi_spec)}
    post = routes["POST"]
    # allOf merge of Money + inline → amount/currency/method
    field_names = {f.name for f in post.body.fields}
    assert {"amount", "currency", "method"} <= field_names
    amount = next(f for f in post.body.fields if f.name == "amount")
    assert amount.type is FieldType.INTEGER


def test_security_makes_route_auth_required(openapi_spec):
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    assert post.auth_required is True


def test_response_schema_is_captured(openapi_spec):
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    resp = next(r for r in post.responses if r.status == 201)
    assert resp.body is not None
    assert {f.name for f in resp.body.fields} == {"id", "status"}


def test_path_param_from_shared_parameters(openapi_spec):
    get = next(r for r in routes_from_spec(openapi_spec) if r.method == "GET")
    assert [p.name for p in get.path_params] == ["payment_id"]


def test_source_is_labelled_openapi(openapi_spec):
    assert all(r.source is InputSource.OPENAPI for r in routes_from_spec(openapi_spec))


def test_summary_becomes_docstring(openapi_spec):
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    assert post.docstring == "Create a payment"


# --- loading (PRD §9.2) ------------------------------------------------------------

def test_load_spec_from_json_file(tmp_path, openapi_spec):
    p = tmp_path / "openapi.json"
    p.write_text(json.dumps(openapi_spec), encoding="utf-8")
    assert load_spec(str(p))["openapi"] == "3.0.3"


def test_load_spec_from_yaml_file(tmp_path):
    p = tmp_path / "openapi.yaml"
    p.write_text("openapi: 3.0.3\npaths: {}\n", encoding="utf-8")
    assert load_spec(str(p))["openapi"] == "3.0.3"


def test_load_missing_spec_raises():
    with pytest.raises(OpenApiError):
        load_spec("/does/not/exist/openapi.json")
