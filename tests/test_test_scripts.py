"""Three-tier test-script generation (PRD §8 step 6, §8.6, §14)."""

from __future__ import annotations

from postman_mcp.engine.tests import build_test_script
from postman_mcp.models import (
    BodyField,
    BodyModel,
    FieldType,
    ResponseModel,
    RouteModel,
)


def _route_with_response_body():
    return RouteModel(
        method="POST",
        path="/payments",
        body=BodyModel(fields=[BodyField(name="amount", type=FieldType.INTEGER)]),
        responses=[
            ResponseModel(
                status=201,
                body=BodyModel(fields=[BodyField(name="id", type=FieldType.STRING)]),
            )
        ],
    )


def test_status_tier_always_present():
    script = build_test_script(RouteModel(method="GET", path="/x"))
    assert 'pm.response.to.have.status(200)' in script


def test_status_tier_uses_declared_2xx():
    script = build_test_script(_route_with_response_body())
    assert "status(201)" in script


def test_schema_tier_checks_response_fields():
    script = build_test_script(_route_with_response_body())
    assert "response matches schema" in script
    assert 'to.have.property("id")' in script


def test_business_tier_off_by_default():
    script = build_test_script(_route_with_response_body())
    assert "business" not in script


def test_business_tier_emitted_when_enabled():
    script = build_test_script(_route_with_response_body(), business=True)
    assert "business(amount > 0)" in script
    assert "verify before trust" in script


def test_business_tier_noop_without_amount_field():
    route = RouteModel(
        method="POST",
        path="/users",
        body=BodyModel(fields=[BodyField(name="email", type=FieldType.STRING)]),
    )
    # No amount/price field → no business assertion even when enabled.
    assert "business(" not in build_test_script(route, business=True)
