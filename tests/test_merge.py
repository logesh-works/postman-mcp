"""Whole-collection merge: match, idempotency, preservation, soft delete."""

from __future__ import annotations

from postman_mcp.engine.builder import build_request_item
from postman_mcp.models import ChangeType
from postman_mcp.postman.merge import (
    apply_route,
    compute_diff,
    ensure_folder,
    find_item,
    item_key,
    purge,
    soft_deprecate,
)


def test_item_key_extracts_method_and_path():
    # A literal id stays literal; a {param} placeholder normalizes.
    literal = {"request": {"method": "get", "url": {"raw": "{{base_url}}/users/123"}}}
    assert item_key(literal) == "GET:/users/123"

    templated = {"request": {"method": "get", "url": {"raw": "{{base_url}}/users/{id}"}}}
    assert item_key(templated) == "GET:/users/{param}"


def test_ensure_folder_creates_nested_path(empty_collection):
    items = ensure_folder(empty_collection, "auth/oauth")
    items.append({"name": "x", "request": {"method": "GET", "url": {"raw": "{{base_url}}/x"}}})
    auth = next(i for i in empty_collection["item"] if i["name"] == "auth")
    oauth = next(i for i in auth["item"] if i["name"] == "oauth")
    assert oauth["item"][0]["name"] == "x"


def test_apply_route_creates_new(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    result = apply_route(empty_collection, built, create_payment_route, "payments")
    assert result is ChangeType.NEW
    assert find_item(empty_collection, create_payment_route.key) is not None


def test_apply_route_is_idempotent(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")
    second = apply_route(empty_collection, built, create_payment_route, "payments")
    assert second is ChangeType.MODIFIED
    # No duplicate: exactly one matching request across the whole collection.
    matches = 0
    for folder in empty_collection["item"]:
        matches += sum(1 for i in folder.get("item", []) if i.get("request"))
    assert matches == 1


def test_human_scripts_and_examples_preserved(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")

    # A human adds a test script + a curated saved example + edits the description.
    _, _, item = find_item(empty_collection, create_payment_route.key)
    item["event"] = [{"listen": "test", "script": {"exec": ["// human test"]}}]
    item["response"] = [{"name": "human example", "code": 201}]
    item["request"]["description"] = "Hand-written docs."

    # Re-sync from code.
    apply_route(empty_collection, built, create_payment_route, "payments")
    _, _, after = find_item(empty_collection, create_payment_route.key)
    assert after["event"] == [{"listen": "test", "script": {"exec": ["// human test"]}}]
    assert after["response"] == [{"name": "human example", "code": 201}]
    assert after["request"]["description"] == "Hand-written docs."


def test_structural_fields_updated_from_code(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")

    # Code changes: drop auth. Structure must follow code.
    create_payment_route.auth_required = False
    rebuilt = build_request_item(create_payment_route)
    apply_route(empty_collection, rebuilt, create_payment_route, "payments")
    _, _, after = find_item(empty_collection, create_payment_route.key)
    assert "auth" not in after["request"]


def test_compute_diff_new_then_modified(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    diff = compute_diff(empty_collection, built, create_payment_route, "payments")
    assert diff.change is ChangeType.NEW
    assert diff.source.value == "openapi"

    apply_route(empty_collection, built, create_payment_route, "payments")
    diff2 = compute_diff(empty_collection, built, create_payment_route, "payments")
    assert diff2.change is ChangeType.MODIFIED


def test_compute_diff_flags_low_confidence(empty_collection, get_payment_route):
    from postman_mcp.models import BodyModel

    get_payment_route.body = BodyModel(low_confidence=True)
    built = build_request_item(get_payment_route)
    diff = compute_diff(empty_collection, built, get_payment_route, "/")
    assert diff.low_confidence is True


def test_soft_deprecate_marks_not_deletes(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")
    assert soft_deprecate(empty_collection, create_payment_route.key) is True
    _, _, item = find_item(empty_collection, create_payment_route.key)
    assert item["name"].startswith("[DEPRECATED] ")


def test_purge_hard_deletes(empty_collection, create_payment_route):
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")
    assert purge(empty_collection, create_payment_route.key) is True
    assert find_item(empty_collection, create_payment_route.key) is None
