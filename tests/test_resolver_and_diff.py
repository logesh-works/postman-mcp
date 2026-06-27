"""Input resolver (per-route mixing, target matching) + diff rendering."""

from __future__ import annotations

import json

from postman_mcp.config.store import ProjectConfig
from postman_mcp.diff.render import render_plan, render_status
from postman_mcp.input.resolver import match_target, resolve_routes
from postman_mcp.models import (
    ChangeType,
    InputSource,
    RequestDiff,
    RouteModel,
    SyncPlan,
)


# --- resolver: per-route mixing -----------------------------------------

def test_resolve_openapi_then_code_fills_gaps(tmp_path, openapi_spec):
    # Spec covers POST /payments and GET /payments/{id}.
    (tmp_path / "openapi.json").write_text(json.dumps(openapi_spec), encoding="utf-8")
    # Express code adds an extra route the spec doesn't have.
    (tmp_path / "extra.js").write_text(
        "app.delete('/webhooks/:id', (req, res) => res.end());", encoding="utf-8"
    )
    config = ProjectConfig(
        framework="express",
        inputMode="openapi",
        openApiSource=str(tmp_path / "openapi.json"),
    )
    result = resolve_routes(config, tmp_path)
    keys = {r.key: r for r in result.routes}
    assert "POST:/payments" in keys
    assert "DELETE:/webhooks/{param}" in keys
    # Spec route is labelled openapi; the code-only route is labelled code.
    assert keys["POST:/payments"].source is InputSource.OPENAPI
    assert keys["DELETE:/webhooks/{param}"].source is InputSource.CODE


def test_resolve_unreachable_spec_falls_back_with_note(tmp_path):
    config = ProjectConfig(
        framework="fastapi",
        inputMode="openapi",
        openApiSource=str(tmp_path / "missing.json"),
    )
    result = resolve_routes(config, tmp_path)
    assert any("falling back to code parsing" in n for n in result.notes)


# --- target matching ----------------------------------------------

def _routes():
    return [
        RouteModel(method="POST", path="/payments", code_ref="app.py::create_payment"),
        RouteModel(method="GET", path="/payments/{id}", code_ref="app.py::get_payment"),
    ]


def test_match_target_by_method_route_string():
    matches = match_target(_routes(), "POST /payments")
    assert len(matches) == 1 and matches[0].method == "POST"


def test_match_target_by_function_name():
    matches = match_target(_routes(), "create_payment")
    assert len(matches) == 1 and matches[0].path == "/payments"


def test_match_target_by_path_fragment():
    matches = match_target(_routes(), "payments")
    assert len(matches) == 2  # ambiguous → caller asks the user


# --- diff rendering ------------------------------------------------------

def _new_diff(**kw):
    base = dict(
        change=ChangeType.NEW,
        method="POST",
        path="/payments",
        into="payments",
        source=InputSource.OPENAPI,
        lines=["+ Request    POST {{base_url}}/payments"],
    )
    base.update(kw)
    return RequestDiff(**base)


def test_render_plan_shows_source_and_prompt():
    plan = SyncPlan(collection_id="c1", collection_name="Acme", diffs=[_new_diff()])
    out = render_plan(plan)
    assert "[NEW]" in out and "[openapi]" in out
    assert "Write? [y / n]" in out
    assert "1 new" in out


def test_render_plan_warns_on_non_default_collection():
    plan = SyncPlan(
        collection_id="c1",
        collection_name="Other",
        is_default_collection=False,
        diffs=[_new_diff()],
    )
    out = render_plan(plan)
    assert "NON-DEFAULT" in out and "--confirm" in out


def test_render_plan_flags_low_confidence_and_preserved():
    diff = _new_diff(
        change=ChangeType.MODIFIED,
        source=InputSource.CODE,
        low_confidence=True,
        preserved=["test scripts"],
    )
    out = render_plan(SyncPlan(collection_id="c1", diffs=[diff]))
    assert "lower confidence" in out
    assert "Preserved (human-owned): test scripts" in out


def test_render_plan_lists_skipped():
    plan = SyncPlan(collection_id="c1", diffs=[_new_diff()], skipped=["bad.py: syntax"])
    assert "Skipped" in render_plan(plan)


def test_render_plan_empty_is_up_to_date():
    assert "up to date" in render_plan(SyncPlan(collection_id="c1"))


def test_render_status_has_no_write_prompt():
    plan = SyncPlan(collection_id="c1", diffs=[_new_diff()])
    out = render_status(plan)
    assert "read-only" in out
    assert "Write?" not in out


def test_render_status_no_drift():
    assert "No drift" in render_status(SyncPlan(collection_id="c1"))
