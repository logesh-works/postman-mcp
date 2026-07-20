"""Path A — OpenAPI 3.x → route models."""

from __future__ import annotations

import json

import pytest

from postman_mcp.input.openapi import OpenApiError, _ref_name, load_spec, routes_from_spec
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


def test_body_and_response_take_the_schema_ref_name(openapi_spec):
    # The diff and the engine show this name in the Body/Response columns, so it must be
    # the actual component name (PaymentRequest/PaymentResponse), not a generic
    # "RequestBody"/"Response201" placeholder, whenever the schema is a named $ref.
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    assert post.body.name == "PaymentRequest"
    resp = next(r for r in post.responses if r.status == 201)
    assert resp.body.name == "PaymentResponse"


# --- array/nested/enum DTO name resolution -------------------------------------------


def test_ref_name_direct_ref():
    assert _ref_name({"$ref": "#/components/schemas/UserDto"}) == "UserDto"


def test_ref_name_array_of_ref_keeps_dto_name():
    """``@ApiOkResponse({ type: UserDto, isArray: true })`` serializes to a bare array
    schema whose $ref lives one level down on ``items`` — this must not fall back to a
    generic ``Response200``/``RequestBody`` placeholder."""
    schema = {"type": "array", "items": {"$ref": "#/components/schemas/UserDto"}}
    assert _ref_name(schema) == "UserDto[]"


def test_ref_name_nested_array_of_ref():
    schema = {
        "type": "array",
        "items": {"type": "array", "items": {"$ref": "#/components/schemas/UserDto"}},
    }
    assert _ref_name(schema) == "UserDto[][]"


def test_ref_name_enum_array_has_no_component_to_preserve():
    """An array of an inline enum (no $ref anywhere) has no named component to recover —
    falls back gracefully instead of crashing or fabricating a name."""
    schema = {"type": "array", "items": {"type": "string", "enum": ["a", "b"]}}
    assert _ref_name(schema) is None


def test_ref_name_plain_object_without_ref_is_none():
    assert _ref_name({"type": "object", "properties": {}}) is None


def test_nested_object_field_resolves_its_own_properties(openapi_spec):
    """A field that is itself an object (not just the top-level body) must resolve its
    own nested fields, not collapse to an empty/opaque object."""
    openapi_spec["components"]["schemas"]["PaymentRequest"]["allOf"][1]["properties"][
        "billingAddress"
    ] = {
        "type": "object",
        "properties": {"city": {"type": "string"}, "zip": {"type": "string"}},
    }
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    address = next(f for f in post.body.fields if f.name == "billingAddress")
    assert address.type is FieldType.OBJECT
    assert {f.name for f in address.fields} == {"city", "zip"}


def test_array_of_objects_field_resolves_item_fields(openapi_spec):
    """An array field whose items are an inline object (``items: OrderItemDto[]``, not a
    bare top-level array response) must resolve the item's own fields."""
    openapi_spec["components"]["schemas"]["PaymentRequest"]["allOf"][1]["properties"][
        "items"
    ] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"sku": {"type": "string"}, "quantity": {"type": "integer"}},
        },
    }
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    items_field = next(f for f in post.body.fields if f.name == "items")
    assert items_field.type is FieldType.ARRAY
    assert items_field.items.type is FieldType.OBJECT
    assert {f.name for f in items_field.items.fields} == {"sku", "quantity"}


def test_array_response_schema_preserves_dto_name_end_to_end(openapi_spec):
    """The same fix, exercised through the real route mapper: a GET returning
    ``UserDto[]`` must show up as ``resp.body.name == "UserDto[]"``, not ``Response200``."""
    openapi_spec["components"]["schemas"]["UserDto"] = {
        "type": "object", "properties": {"id": {"type": "string"}},
    }
    openapi_spec["paths"]["/users"] = {
        "get": {
            "operationId": "list_users",
            "responses": {
                "200": {
                    "description": "OK",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/UserDto"},
                            }
                        }
                    },
                }
            },
        }
    }
    routes = routes_from_spec(openapi_spec)
    get_users = next(r for r in routes if r.path == "/users" and r.method == "GET")
    resp = next(r for r in get_users.responses if r.status == 200)
    assert resp.body.name == "UserDto[]"


def test_path_param_from_shared_parameters(openapi_spec):
    get = next(r for r in routes_from_spec(openapi_spec) if r.method == "GET")
    assert [p.name for p in get.path_params] == ["payment_id"]


def test_source_is_labelled_openapi(openapi_spec):
    assert all(r.source is InputSource.OPENAPI for r in routes_from_spec(openapi_spec))


def test_summary_becomes_docstring(openapi_spec):
    post = next(r for r in routes_from_spec(openapi_spec) if r.method == "POST")
    assert post.docstring == "Create a payment"


# --- loading ------------------------------------------------------------

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
