"""Express code parser (PRD §9.4) — the most important fallback (no native spec).

Express has no native type system, so body inference is best-effort and every route is
flagged **lower confidence** in the diff when no body type is found (PRD §9.4, §18).
Regex/heuristic over ``.js`` / ``.ts`` files: ``app.get('/path', ...)`` /
``router.post('/path', requireAuth, handler)``.
"""

from __future__ import annotations

import re
from pathlib import Path

from postman_mcp.input.parsers.base import iter_source_files, read_text
from postman_mcp.models import (
    BodyModel,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)

# app.get('/path', mw1, handler)  /  router.post("/x", ...)
_ROUTE = re.compile(
    r"""\b(?:app|router)\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['"`]([^'"`]+)['"`]([^)]*)\)""",
    re.IGNORECASE,
)
_PATH_PARAM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_AUTH_HINTS = ("requireauth", "isauthenticated", "authenticate", "ensureauth", "auth", "protect", "verifytoken")
# req.body.<field> usages give us best-effort body field names.
_BODY_FIELD = re.compile(r"req\.body\.([A-Za-z_][A-Za-z0-9_]*)")


def parse(project_root: Path | str) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    routes: list[RouteModel] = []
    skipped: list[str] = []
    for path in iter_source_files(root, (".js", ".ts", ".mjs", ".cjs")):
        text = read_text(path)
        rel = path.relative_to(root).as_posix()
        body_fields = _body_field_names(text)
        for match in _ROUTE.finditer(text):
            method = match.group(1).upper()
            route_path = match.group(2)
            rest = match.group(3) or ""
            routes.append(
                _build_route(method, route_path, rest, body_fields, rel)
            )
    return routes, skipped


def _build_route(
    method: str, path: str, rest: str, body_fields: list[str], rel: str
) -> RouteModel:
    path_params = [
        Param(name=name, location=ParamLocation.PATH, required=True)
        for name in _PATH_PARAM.findall(path)
    ]
    auth = any(h in rest.lower() for h in _AUTH_HINTS)

    body = None
    if method in ("POST", "PUT", "PATCH"):
        from postman_mcp.models import BodyField

        fields = [BodyField(name=n, required=False) for n in body_fields]
        # No native types → lower confidence regardless (PRD §9.4).
        body = BodyModel(name="RequestBody", fields=fields, low_confidence=True)

    success = 201 if method == "POST" else 200
    return RouteModel(
        method=method,
        path=path,
        path_params=path_params,
        body=body,
        responses=[ResponseModel(status=success)],
        auth_required=auth,
        code_ref=f"{rel}",
        source=InputSource.CODE,
    )


def _body_field_names(text: str) -> list[str]:
    """Best-effort body fields from ``req.body.X`` usages (PRD §9.4)."""
    seen: list[str] = []
    for name in _BODY_FIELD.findall(text):
        if name not in seen:
            seen.append(name)
    return seen
