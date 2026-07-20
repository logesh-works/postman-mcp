"""Whole-collection merge: match, idempotency, preservation, soft delete."""

from __future__ import annotations

import copy

from postman_mcp.engine.builder import build_request_item
from postman_mcp.models import ChangeType
from postman_mcp.postman.merge import (
    apply_route,
    compute_diff,
    ensure_folder,
    find_item,
    item_key,
    items_equivalent,
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
    first = apply_route(empty_collection, built, create_payment_route, "payments")
    assert first is ChangeType.NEW
    # Re-applying the exact same built item is a true no-op — reported UNCHANGED,
    # not a false "modified" (the bug: every re-sync used to claim everything changed).
    second = apply_route(empty_collection, built, create_payment_route, "payments")
    assert second is ChangeType.UNCHANGED
    # No duplicate: exactly one matching request across the whole collection.
    matches = 0
    for folder in empty_collection["item"]:
        matches += sum(1 for i in folder.get("item", []) if i.get("request"))
    assert matches == 1


def test_apply_route_reports_modified_on_real_change(empty_collection, create_payment_route):
    """The flip side of idempotency: a route whose built item genuinely differs from
    what's live (here, auth dropped) must still be reported MODIFIED, not UNCHANGED."""
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")

    create_payment_route.auth_required = False
    rebuilt = build_request_item(create_payment_route)
    result = apply_route(empty_collection, rebuilt, create_payment_route, "payments")
    assert result is ChangeType.MODIFIED


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


def test_compute_diff_new_then_unchanged(empty_collection, create_payment_route):
    """New the first time; re-diffing the identical route/build against what was just
    written is UNCHANGED — re-running a sync with zero code changes must not claim
    drift that doesn't exist."""
    built = build_request_item(create_payment_route)
    diff = compute_diff(empty_collection, built, create_payment_route, "payments")
    assert diff.change is ChangeType.NEW
    assert diff.source.value == "openapi"

    apply_route(empty_collection, built, create_payment_route, "payments")
    diff2 = compute_diff(empty_collection, built, create_payment_route, "payments")
    assert diff2.change is ChangeType.UNCHANGED


def test_compute_diff_reports_modified_when_body_changes(empty_collection, create_payment_route):
    """A route that genuinely changes (a new required field) must still surface as
    MODIFIED — the UNCHANGED fix must not swallow real drift."""
    from postman_mcp.models import BodyField, FieldType

    built = build_request_item(create_payment_route)
    apply_route(empty_collection, built, create_payment_route, "payments")

    create_payment_route.body.fields.append(
        BodyField(name="note", type=FieldType.STRING, required=False)
    )
    rebuilt = build_request_item(create_payment_route)
    diff2 = compute_diff(empty_collection, rebuilt, create_payment_route, "payments")
    assert diff2.change is ChangeType.MODIFIED


def test_compute_diff_ignores_header_reorder_and_whitespace(empty_collection, create_payment_route):
    """Cosmetic differences — header order, JSON body whitespace/key order — must not
    be reported as drift.

    ``apply_route``'s NEW branch stores the built dict *by reference* — passing a
    ``copy.deepcopy`` keeps ``built`` (used below for the comparison) independent from
    the stored "live" copy we then mutate; otherwise they'd be the same object and the
    assertion would pass vacuously.
    """
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, copy.deepcopy(built), create_payment_route, "payments")

    _, _, live = find_item(empty_collection, create_payment_route.key)
    # Reverse header order and reformat the JSON body with different whitespace/order —
    # semantically identical, textually different.
    live["request"]["header"] = list(reversed(live["request"]["header"]))
    import json as _json

    body_obj = _json.loads(live["request"]["body"]["raw"])
    live["request"]["body"]["raw"] = _json.dumps(
        dict(reversed(list(body_obj.items()))), indent=4
    )

    diff = compute_diff(empty_collection, built, create_payment_route, "payments")
    assert diff.change is ChangeType.UNCHANGED


def test_compute_diff_ignores_postman_generated_ids(empty_collection, create_payment_route):
    """An ``id``/``_postman_id`` Postman stamps onto a saved item/response on write must
    never be mistaken for a real difference on the next diff. See the deepcopy note on
    ``test_compute_diff_ignores_header_reorder_and_whitespace`` above."""
    built = build_request_item(create_payment_route)
    apply_route(empty_collection, copy.deepcopy(built), create_payment_route, "payments")

    _, _, live = find_item(empty_collection, create_payment_route.key)
    live["id"] = "postman-generated-item-id"
    live["_postman_id"] = "another-generated-id"
    for resp in live.get("response", []):
        resp["id"] = "postman-generated-response-id"
        resp["uid"] = "postman-generated-response-uid"

    diff = compute_diff(empty_collection, built, create_payment_route, "payments")
    assert diff.change is ChangeType.UNCHANGED


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


# --- items_equivalent: the equality check behind NEW/UNCHANGED/MODIFIED ---------------


def _item(method="GET", raw="{{base_url}}/x", headers=None, body=None, responses=None):
    request = {"method": method, "header": headers or [], "url": {"raw": raw}}
    if body is not None:
        request["body"] = body
    item = {"name": "x", "request": request}
    if responses is not None:
        item["response"] = responses
    return item


def test_items_equivalent_true_for_identical_items():
    a = _item()
    b = _item()
    assert items_equivalent(a, b) is True


def test_items_equivalent_ignores_examples_reordering():
    """Saved examples (responses) in a different order are still the same examples."""
    responses = [
        {"name": "200 OK", "code": 200, "header": [], "body": "{}"},
        {"name": "404 Not Found", "code": 404, "header": [], "body": "{}"},
    ]
    a = _item(responses=responses)
    b = _item(responses=list(reversed(responses)))
    assert items_equivalent(a, b) is True


def test_items_equivalent_detects_response_body_change():
    a = _item(responses=[{"name": "200", "code": 200, "header": [], "body": '{"a": 1}'}])
    b = _item(responses=[{"name": "200", "code": 200, "header": [], "body": '{"a": 2}'}])
    assert items_equivalent(a, b) is False


def test_items_equivalent_ignores_absent_vs_empty_lists():
    """An item that omits ``header``/``response`` entirely is the same as one that
    states them as an explicit empty list — both mean 'nothing there'."""
    a = {"name": "x", "request": {"method": "GET", "url": {"raw": "{{base_url}}/x"}}}
    b = _item(headers=[], responses=[])
    assert items_equivalent(a, b) is True


def test_items_equivalent_detects_method_change():
    a = _item(method="GET")
    b = _item(method="POST")
    assert items_equivalent(a, b) is False


def test_items_equivalent_detects_header_disabled_flip():
    """A header flag change (required → optional) is real drift, not noise — the
    key/value-only comparison this replaced would have missed it."""
    a = _item(headers=[{"key": "X-Trace", "value": "1", "disabled": False}])
    b = _item(headers=[{"key": "X-Trace", "value": "1", "disabled": True}])
    assert items_equivalent(a, b) is False


# --- url.variable: Postman auto-derives it for :param routes -------------------------
#
# The LLM-authored request shape (contract/playbook/skills/request-builder.md) never
# writes a `variable` array — path params stay literal in `path`/`raw` only. Postman's
# API auto-derives one (`[{"key": "id"}]`) the moment such a collection round-trips
# through it. These tests build that "built" item by hand (not via
# ``build_request_item``, which — for the *parser* engine's own route models — already
# populates `variable` itself and so never hits this gap) to reproduce exactly what the
# real LLM-authored artifacts look like.


def _no_variable_built_item():
    return _item(
        method="GET",
        raw="{{base_url}}/payments/:payment_id",
    )


def test_path_param_route_reports_unchanged_after_postmans_auto_added_variable(
    empty_collection, get_payment_route,
):
    """Postman auto-injects ``url.variable`` into any ``:param``/``{param}`` route as
    soon as it round-trips through the API, even though the LLM-authored item never
    included one. Without accounting for this, every path-param route synced through
    ``sync_files`` would show MODIFIED forever, even with zero real drift.

    ``apply_route``'s NEW branch stores the built dict *by reference*, so each call
    below passes a fresh ``copy.deepcopy`` — otherwise mutating "live" would silently
    mutate ``built`` too (they'd be the same object) and the test would pass
    vacuously regardless of the fix.
    """
    built = _no_variable_built_item()
    apply_route(empty_collection, copy.deepcopy(built), get_payment_route, "/")

    _, _, live = find_item(empty_collection, get_payment_route.key)
    live["request"]["url"]["variable"] = [{"key": "payment_id"}]

    diff = compute_diff(empty_collection, built, get_payment_route, "/")
    assert diff.change is ChangeType.UNCHANGED


def test_merge_preserves_human_set_path_variable_value(empty_collection, get_payment_route):
    """A write must not silently discard a variable's value/description a human set in
    Postman just because the code-built url doesn't restate it."""
    built = _no_variable_built_item()
    apply_route(empty_collection, copy.deepcopy(built), get_payment_route, "/")

    _, _, live = find_item(empty_collection, get_payment_route.key)
    live["request"]["url"]["variable"] = [
        {"key": "payment_id", "value": "pay_123", "description": "A real payment id"}
    ]

    apply_route(empty_collection, copy.deepcopy(built), get_payment_route, "/")
    _, _, after = find_item(empty_collection, get_payment_route.key)
    assert after["request"]["url"]["variable"] == [
        {"key": "payment_id", "value": "pay_123", "description": "A real payment id"}
    ]


def test_merge_lets_code_add_a_variable_if_it_specifies_one(empty_collection, get_payment_route):
    """If the code-built url *does* specify a ``variable`` array, code still wins —
    this is only about not clobbering with an absent one."""
    built = _no_variable_built_item()
    built["request"]["url"]["variable"] = [{"key": "payment_id", "value": "from-code"}]
    apply_route(empty_collection, copy.deepcopy(built), get_payment_route, "/")

    _, _, live = find_item(empty_collection, get_payment_route.key)
    live["request"]["url"]["variable"] = [{"key": "payment_id", "value": "stale"}]

    apply_route(empty_collection, copy.deepcopy(built), get_payment_route, "/")
    _, _, after = find_item(empty_collection, get_payment_route.key)
    assert after["request"]["url"]["variable"] == [{"key": "payment_id", "value": "from-code"}]
