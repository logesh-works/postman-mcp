"""NestJS code parser (PRD §9.4) — decorators over ``.ts`` files.

Routes from ``@Controller('prefix')`` + ``@Post()`` / ``@Get(':id')``; body shapes from
DTO classes (``@Body() dto: CreateUserDto``) with class-validator fields; auth from
``@UseGuards(AuthGuard)``. Heuristic (no TS AST), so types are best-effort (PRD §9.4).
"""

from __future__ import annotations

import re
from pathlib import Path

from postman_mcp.input.parsers.base import iter_source_files, read_text, ts_field_type
from postman_mcp.models import (
    BodyField,
    BodyModel,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)

_CONTROLLER = re.compile(r"@Controller\(\s*['\"`]?([^'\"`)]*)['\"`]?\s*\)")
# http + subpath, optional extra decorators, then methodName(params)
_METHOD = re.compile(
    r"@(Get|Post|Put|Patch|Delete)\(\s*['\"`]?([^'\"`)]*)['\"`]?\s*\)"
    r"([\s\S]{0,200}?)"
    r"\b(\w+)\s*\(([\s\S]*?)\)\s*(?::[^{;]+)?\{",  # methodName(params)<:ret>{
)
_USE_GUARDS = re.compile(r"@UseGuards\(")
_BODY_PARAM = re.compile(r"@Body\(\)\s*\w+\s*:\s*(\w+)")
_PATH_PARAM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_CLASS = re.compile(r"\bclass\s+(\w+)\b[^{]*\{([^}]*)\}")
# one field declaration: `name: string`, allowing `?`/`readonly` and `;`/`,` separators
_FIELD = re.compile(r"(?:readonly\s+)?(\w+)\s*[?!]?\s*:\s*([A-Za-z0-9_\[\]<>]+)")


def parse(project_root: Path | str) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    dtos: dict[str, BodyModel] = {}
    sources: list[tuple[str, str]] = []
    skipped: list[str] = []

    for path in iter_source_files(root, (".ts",)):
        text = read_text(path)
        rel = path.relative_to(root).as_posix()
        sources.append((rel, text))
        _collect_dtos(text, dtos)

    routes: list[RouteModel] = []
    for rel, text in sources:
        controller_prefix = ""
        cm = _CONTROLLER.search(text)
        if cm:
            controller_prefix = cm.group(1).strip("/")
        class_has_guard = bool(_USE_GUARDS.search(text))

        for m in _METHOD.finditer(text):
            http, sub_path, between, _fn, params = m.groups()
            full = "/" + "/".join(p for p in (controller_prefix, sub_path.strip("/")) if p)
            method = http.upper()
            auth = class_has_guard or "@UseGuards(" in between
            body = None
            bm = _BODY_PARAM.search(params)
            if bm and bm.group(1) in dtos:
                body = dtos[bm.group(1)]
            elif method in ("POST", "PUT", "PATCH"):
                body = BodyModel(name="RequestBody", fields=[], low_confidence=True)

            path_params = [
                Param(name=n, location=ParamLocation.PATH, required=True)
                for n in _PATH_PARAM.findall(full)
            ]
            success = 201 if method == "POST" else 200
            routes.append(
                RouteModel(
                    method=method,
                    path=full,
                    path_params=path_params,
                    body=body,
                    responses=[ResponseModel(status=success)],
                    auth_required=auth,
                    code_ref=rel,
                    source=InputSource.CODE,
                )
            )
    return routes, skipped


def _collect_dtos(text: str, dtos: dict[str, BodyModel]) -> None:
    for cm in _CLASS.finditer(text):
        name, body = cm.group(1), cm.group(2)
        fields = [
            BodyField(name=fn, type=ts_field_type(ftype), required=True)
            for fn, ftype in _FIELD.findall(body)
        ]
        if fields:
            dtos[name] = BodyModel(name=name, fields=fields)
