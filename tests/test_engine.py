"""The engine: RouteModel → Postman Collection v2.1 item."""

from __future__ import annotations

import json

from postman_mcp.engine.builder import build_request_item
from postman_mcp.engine.examples import example_body, example_for_field
from postman_mcp.models import BodyField, BodyModel, FieldType


def test_build_item_is_complete(create_payment_route):
    item = build_request_item(create_payment_route, response_style="full")
    req = item["request"]

    # 1. Method + URL with {{base_url}} prefix
    assert req["method"] == "POST"
    assert req["url"]["raw"] == "{{base_url}}/payments"
    # 3. Body present, valid JSON
    body = json.loads(req["body"]["raw"])
    assert set(body) == {"amount", "currency", "method"}
    # 4. Auth header (Bearer {{token}})
    assert req["auth"]["type"] == "bearer"
    # Content-Type added when a body exists
    assert {"key": "Content-Type", "value": "application/json"} in req["header"]
    # 8. Docs from docstring
    assert req["description"] == "Create a new payment."


def test_full_style_includes_declared_and_standard_errors(create_payment_route):
    item = build_request_item(create_payment_route, response_style="full")
    codes = {r["code"] for r in item["response"]}
    # declared 201 + standard error set (401/403 only because auth_required)
    assert 201 in codes
    assert {400, 401, 403, 404, 422, 500} <= codes


def test_minimal_style_is_one_success_one_error(create_payment_route):
    item = build_request_item(create_payment_route, response_style="minimal")
    codes = sorted(r["code"] for r in item["response"])
    assert codes == [201, 400]


def test_single_style_is_one_response_only(create_payment_route):
    item = build_request_item(create_payment_route, response_style="single")
    assert [r["code"] for r in item["response"]] == [201]


def test_single_is_the_default_style(create_payment_route):
    item = build_request_item(create_payment_route)
    assert [r["code"] for r in item["response"]] == [201]


def test_no_auth_route_omits_auth_and_401(get_payment_route):
    item = build_request_item(get_payment_route, response_style="full")
    assert "auth" not in item["request"]
    codes = {r["code"] for r in item["response"]}
    # 401/403 are skipped when the route is not behind auth
    assert 401 not in codes and 403 not in codes


def test_tests_are_off_by_default(create_payment_route):
    item = build_request_item(create_payment_route)
    assert "event" not in item


def test_tests_attached_when_enabled(create_payment_route):
    item = build_request_item(create_payment_route, generate_tests=True)
    assert item["event"][0]["listen"] == "test"
    exec_lines = item["event"][0]["script"]["exec"]
    assert any("pm.test" in line for line in exec_lines)


def test_path_param_becomes_postman_variable(get_payment_route):
    item = build_request_item(get_payment_route)
    url = item["request"]["url"]
    assert ":payment_id" in url["path"]
    assert any(v["key"] == "payment_id" for v in url.get("variable", []))


# --- examples -----------------------------------------------------------

def test_examples_are_name_aware():
    assert example_for_field(BodyField(name="email", type=FieldType.STRING)) == "user@example.com"
    assert example_for_field(BodyField(name="amount", type=FieldType.INTEGER)) == 4200
    assert example_for_field(BodyField(name="created_at", type=FieldType.STRING)).endswith("Z")


def test_examples_are_deterministic():
    body = BodyModel(fields=[BodyField(name="amount", type=FieldType.INTEGER)])
    assert example_body(body) == example_body(body)


def test_nested_object_and_array_examples():
    body = BodyModel(
        fields=[
            BodyField(
                name="items",
                type=FieldType.ARRAY,
                items=BodyField(name="sku", type=FieldType.STRING),
            ),
            BodyField(
                name="meta",
                type=FieldType.OBJECT,
                fields=[BodyField(name="count", type=FieldType.INTEGER)],
            ),
        ]
    )
    example = example_body(body)
    assert isinstance(example["items"], list) and example["items"]
    assert example["meta"] == {"count": 3}
