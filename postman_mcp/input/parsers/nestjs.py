"""NestJS code parser — decorators over ``.ts`` files.

Routes from ``@Controller('prefix')`` + ``@Post()`` / ``@Get(':id')``; body shapes from
DTO classes (``@Body() dto: CreateUserDto``) with class-validator fields; headers from
``@Headers('x-api-key') key: string``; auth from ``@UseGuards(AuthGuard)``. Heuristic (no
TS AST), so types are best-effort.

DTO class bodies are extracted with a brace-depth walker, not a regex stopping at the
first ``}`` — a single property decorated with an object-literal argument (e.g.
``@ApiProperty({ type: String })``) would otherwise truncate the class silently. Field
extraction then strips decorator call arguments before matching ``name: type`` so a key
inside one of those object literals (``type: String`` above) is never mistaken for a DTO
field.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from postman_mcp.input.parsers.base import read_text, source_files, ts_field_type
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
_HEADER_PARAM = re.compile(
    r"""@Headers\(\s*['"`]([^'"`)]+)['"`]\s*\)\s*\w+\s*[?!]?\s*:\s*([A-Za-z0-9_\[\]<>]+)"""
)
_PATH_PARAM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_CLASS_HEADER = re.compile(r"\bclass\s+(\w+)\b[^{]*\{")
# one field declaration: `name: string`, allowing `?`/`readonly` and `;`/`,` separators
_FIELD = re.compile(r"(?:readonly\s+)?(\w+)\s*[?!]?\s*:\s*([A-Za-z0-9_\[\]<>]+)")
# decorator + its call args, e.g. `@ApiProperty({ type: String })` — stripped before
# field extraction so an object-literal key inside the args isn't read as a DTO field.
_DECORATOR_CALL = re.compile(r"@\w+\s*\(")


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    dtos: dict[str, BodyModel] = {}
    sources: list[tuple[str, str]] = []
    skipped: list[str] = []

    for path in source_files(root, (".ts",), only_files):
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
            headers = [
                Param(name=hname, location=ParamLocation.HEADER, type=ts_field_type(htype), required=True)
                for hname, htype in _HEADER_PARAM.findall(params)
            ]
            success = 201 if method == "POST" else 200
            routes.append(
                RouteModel(
                    method=method,
                    path=full,
                    path_params=path_params,
                    headers=headers,
                    body=body,
                    responses=[ResponseModel(status=success)],
                    auth_required=auth,
                    code_ref=rel,
                    source=InputSource.CODE,
                )
            )
    return routes, skipped


def _extract_braced(text: str, open_idx: int) -> tuple[str, int]:
    """Depth-aware match from a ``{`` at ``open_idx`` to its real closing brace."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
    return text[open_idx + 1 :], len(text)


def _strip_decorator_args(text: str) -> str:
    """Remove ``@Decorator(...)`` call arguments, keeping everything else intact."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        m = _DECORATOR_CALL.match(text, i)
        if m:
            depth = 0
            j = m.end() - 1  # the '(' itself
            while j < n:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _collect_dtos(text: str, dtos: dict[str, BodyModel]) -> None:
    for cm in _CLASS_HEADER.finditer(text):
        name = cm.group(1)
        open_idx = cm.end() - 1  # the '{' the header regex matched
        body, _ = _extract_braced(text, open_idx)
        stripped = _strip_decorator_args(body)
        fields = [
            BodyField(name=fn, type=ts_field_type(ftype), required=True)
            for fn, ftype in _FIELD.findall(stripped)
        ]
        if fields:
            dtos[name] = BodyModel(name=name, fields=fields)
