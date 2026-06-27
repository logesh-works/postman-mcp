"""The engine — one normalized route model → one Postman Collection v2.1 item (PRD §8).

Pipeline (PRD §8 steps 1–8):
1. Method + URL (``{{base_url}}`` prefix)      5. Responses (one per declared status)
2. Params (path/query/header)                  6. Test scripts (status + schema)
3. Request body (typed → example)              7. Examples (reused across request+saved)
4. Auth headers (Bearer {{token}})             8. Docs (from docstring)

Output conforms to the Postman Collection v2.1 item schema:
``{ name, request{method,header,url,body,auth,description}, response[], event[] }``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from postman_mcp.engine.examples import example_body, example_for_param
from postman_mcp.engine.tests import build_test_script
from postman_mcp.models import BodyModel, ResponseModel, RouteModel

# The standard error set every synced API gets (PRD §8 step 5, §14).
_STANDARD_ERRORS = (400, 401, 403, 404, 422, 500)
_ERROR_DESCRIPTIONS = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


def build_request_item(
    route: RouteModel,
    *,
    generate_tests: bool = False,
    response_style: str = "minimal",
    business_tests: bool = False,
) -> dict[str, Any]:
    """Assemble the Collection v2.1 item for a route (PRD §8).

    ``response_style="minimal"`` saves one success + one error response; ``"full"`` saves
    every declared 2xx plus the standard error set. Test-script events are attached only
    when ``generate_tests`` is true (owner preference: off by default).
    """
    request: dict[str, Any] = {
        "method": route.method.upper(),
        "header": _headers(route),
        "url": _url(route),
        "description": route.docstring or "",
    }

    # 3. Request body
    if route.body is not None:
        request["body"] = _body(route.body)

    # 4. Auth headers
    if route.auth_required:
        request["auth"] = {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}],
        }

    item: dict[str, Any] = {
        "name": _item_name(route),
        "request": request,
        # 5. Responses (saved)
        "response": _responses(route, request, response_style),
    }
    # 6. Test scripts — only when explicitly enabled.
    if generate_tests:
        item["event"] = [_test_event(route, business_tests)]
    return item


def _item_name(route: RouteModel) -> str:
    return f"{route.method.upper()} {route.path}"


def _url(route: RouteModel) -> dict[str, Any]:
    """Step 1 — ``{{base_url}}`` + path; query params attached (PRD §8 step 1/2)."""
    raw_path = route.path.lstrip("/")
    segments = raw_path.split("/") if raw_path else []
    path_segments = [
        (":" + s.strip("{}") if s.startswith("{") and s.endswith("}") else s)
        for s in segments
    ]
    url: dict[str, Any] = {
        "raw": "{{base_url}}/" + raw_path,
        "host": ["{{base_url}}"],
        "path": path_segments,
    }
    if route.query_params:
        url["query"] = [
            {"key": p.name, "value": example_for_param(p), "disabled": not p.required}
            for p in route.query_params
        ]
    if route.path_params:
        url["variable"] = [
            {"key": p.name, "value": example_for_param(p)} for p in route.path_params
        ]
    return url


def _headers(route: RouteModel) -> list[dict[str, Any]]:
    headers = [
        {"key": p.name, "value": example_for_param(p), "disabled": not p.required}
        for p in route.headers
    ]
    if route.body is not None:
        headers.insert(0, {"key": "Content-Type", "value": "application/json"})
    return headers


def _body(body: BodyModel) -> dict[str, Any]:
    """Step 3 — typed body → JSON example (PRD §8 step 3, §8.3)."""
    example = example_body(body)
    return {
        "mode": "raw",
        "raw": json.dumps(example, indent=2),
        "options": {"raw": {"language": "json"}},
    }


def _responses(
    route: RouteModel, request: dict[str, Any], style: str = "minimal"
) -> list[dict[str, Any]]:
    """Step 5 — saved responses (PRD §8 step 5).

    ``minimal`` (default): one success + one error. ``full``: every declared 2xx plus
    the standard error set.
    """
    declared_2xx = [r for r in route.responses if 200 <= r.status < 300]

    if style == "minimal":
        saved: list[dict[str, Any]] = []
        if declared_2xx:
            saved.append(_saved_response(route, request, declared_2xx[0]))
        else:
            default = 201 if route.method.upper() == "POST" else 200
            saved.append(
                _saved_response(
                    route, request, ResponseModel(status=default, description="Success")
                )
            )
        # one representative error response
        saved.append(
            _saved_response(
                route, request, ResponseModel(status=400, description="Bad Request")
            )
        )
        return saved

    # "full" — every declared response + the standard error set (PRD §8 step 5, §14).
    saved = []
    declared_codes = {r.status for r in route.responses}
    for resp in route.responses:
        saved.append(_saved_response(route, request, resp))
    for code in _STANDARD_ERRORS:
        if code in declared_codes:
            continue
        if code in (401, 403) and not route.auth_required:
            continue
        saved.append(
            _saved_response(
                route, request, ResponseModel(status=code, description=_ERROR_DESCRIPTIONS[code])
            )
        )
    return saved


def _saved_response(
    route: RouteModel, request: dict[str, Any], resp: ResponseModel
) -> dict[str, Any]:
    code = resp.status
    name = resp.description or _ERROR_DESCRIPTIONS.get(code, str(code))
    if resp.body is not None and resp.body.fields:
        body_text = json.dumps(example_body(resp.body), indent=2)
    elif 200 <= code < 300:
        body_text = "{}"
    else:
        # Standard framework-style error envelope (PRD §8 step 5).
        body_text = json.dumps({"detail": name}, indent=2)
    return {
        "name": f"{code} {name}",
        "originalRequest": request,
        "status": name,
        "code": code,
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": body_text,
        "_postman_previewlanguage": "json",
    }


def _test_event(route: RouteModel, business: bool) -> dict[str, Any]:
    """Step 6 — test script as a Postman ``test`` event (PRD §8 step 6)."""
    script = build_test_script(route, business=business)
    return {
        "listen": "test",
        "script": {"type": "text/javascript", "exec": script.split("\n")},
    }
