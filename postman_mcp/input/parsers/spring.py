"""Spring (Java) code parser — class + method request-mapping composition.

A Spring route's URL is the class-level ``@RequestMapping("/api")`` joined with the
method-level ``@GetMapping("/x")`` / ``@RequestMapping(value="/x", method=...)``, plus an
optional ``server.servlet.context-path`` from ``application.properties`` / ``.yml``.
Reading only the method annotation drops the class prefix and the context path.

Regex/heuristic over ``.java`` (no Java AST dependency). Request bodies come from
``@RequestBody Dto`` resolved against the DTO class's fields; types are best-effort.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from postman_mcp.input.parsers.base import read_text, source_files
from postman_mcp.models import (
    BodyField,
    BodyModel,
    FieldType,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)

_CLASS = re.compile(r"\b(?:public\s+|abstract\s+|final\s+)*(?:class|interface)\s+(\w+)")
_MAPPING = re.compile(
    r"@(Get|Post|Put|Patch|Delete|Request)Mapping\b(?:\s*\(([^)]*)\))?"
)
_PATH_PARAM = re.compile(r"\{(\w+)\}")
_REQUEST_BODY = re.compile(r"@RequestBody\s+(?:final\s+)?([\w<>]+)\s+\w+")
_FIELD = re.compile(
    r"(?:private|public|protected)\s+(?:final\s+)?([\w<>\[\]]+)\s+(\w+)\s*(?:=|;)"
)
_CONTEXT_PATH_PROPS = re.compile(r"server\.servlet\.context-path\s*[=:]\s*(\S+)")

_SHORTHAND_METHOD = {
    "Get": "GET", "Post": "POST", "Put": "PUT", "Patch": "PATCH", "Delete": "DELETE",
}
_JAVA_TYPE = {
    "String": FieldType.STRING, "UUID": FieldType.STRING,
    "int": FieldType.INTEGER, "Integer": FieldType.INTEGER,
    "long": FieldType.INTEGER, "Long": FieldType.INTEGER,
    "double": FieldType.NUMBER, "Double": FieldType.NUMBER,
    "float": FieldType.NUMBER, "Float": FieldType.NUMBER, "BigDecimal": FieldType.NUMBER,
    "boolean": FieldType.BOOLEAN, "Boolean": FieldType.BOOLEAN,
}


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    context_path = _detect_context_path(root)

    # Pass 1: collect DTO field shapes across the whole project (a @RequestBody type is
    # usually declared in another file).
    dtos: dict[str, BodyModel] = {}
    for path in source_files(root, (".java",), None):
        _collect_dtos(read_text(path), dtos)

    routes: list[RouteModel] = []
    skipped: list[str] = []
    for path in source_files(root, (".java",), only_files):
        text = read_text(path)
        rel = path.relative_to(root).as_posix()
        routes.extend(_parse_controller(text, rel, context_path, dtos))
    return routes, skipped


def _parse_controller(
    text: str, rel: str, context_path: str, dtos: dict[str, BodyModel]
) -> list[RouteModel]:
    class_match = _CLASS.search(text)
    if not class_match:
        return []
    class_start = class_match.start()

    # Class-level prefix: a mapping annotation positioned above the class declaration.
    class_prefix = ""
    for m in _MAPPING.finditer(text):
        if m.start() < class_start:
            class_prefix = _mapping_path(m.group(2) or "")
        else:
            break

    method_anns = [m for m in _MAPPING.finditer(text) if m.start() >= class_start]
    routes: list[RouteModel] = []
    for i, m in enumerate(method_anns):
        kind, args = m.group(1), m.group(2) or ""
        region_end = method_anns[i + 1].start() if i + 1 < len(method_anns) else len(text)
        region = text[m.start():region_end]

        leaf = _mapping_path(args)
        path = "/" + "/".join(
            p.strip("/") for p in (context_path, class_prefix, leaf) if p.strip("/")
        )
        methods = _mapping_methods(kind, args)
        path_params = [
            Param(name=n, location=ParamLocation.PATH, required=True)
            for n in _PATH_PARAM.findall(path)
        ]
        body = None
        bm = _REQUEST_BODY.search(region)
        if bm:
            body = dtos.get(_base_type(bm.group(1)))

        for method in methods:
            routes.append(
                RouteModel(
                    method=method,
                    path=path,
                    path_params=path_params,
                    body=body if method in ("POST", "PUT", "PATCH") else None,
                    responses=[ResponseModel(status=201 if method == "POST" else 200)],
                    code_ref=rel,
                    source=InputSource.CODE,
                )
            )
    return routes


def _mapping_path(args: str) -> str:
    m = re.search(r'(?:value|path)\s*=\s*"([^"]*)"', args)
    if m:
        return m.group(1)
    m = re.search(r'"([^"]*)"', args)  # positional value
    return m.group(1) if m else ""


def _mapping_methods(kind: str, args: str) -> list[str]:
    if kind in _SHORTHAND_METHOD:
        return [_SHORTHAND_METHOD[kind]]
    # @RequestMapping(method = RequestMethod.GET) — possibly several; default GET.
    methods = re.findall(r"RequestMethod\.(\w+)", args)
    return [m.upper() for m in methods] or ["GET"]


def _collect_dtos(text: str, dtos: dict[str, BodyModel]) -> None:
    for cm in _CLASS.finditer(text):
        name = cm.group(1)
        brace = text.find("{", cm.end())
        if brace == -1:
            continue
        body, _ = _extract_braced(text, brace)
        fields = [
            BodyField(name=fname, type=_JAVA_TYPE.get(_base_type(ftype), FieldType.UNKNOWN))
            for ftype, fname in _FIELD.findall(body)
        ]
        if fields:
            dtos[name] = BodyModel(name=name, fields=fields)


def _extract_braced(text: str, open_idx: int) -> tuple[str, int]:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
    return text[open_idx + 1 :], len(text)


def _base_type(java_type: str) -> str:
    """``List<PaymentDto>`` → ``PaymentDto``; ``String`` → ``String``."""
    inner = re.search(r"<\s*([\w]+)\s*>", java_type)
    if inner:
        return inner.group(1)
    return java_type.split("[")[0].strip()


def _detect_context_path(root: Path) -> str:
    for name in ("application.properties", "application.yml", "application.yaml"):
        for path in root.rglob(name):
            m = _CONTEXT_PATH_PROPS.search(read_text(path))
            if m:
                return m.group(1).strip().strip('"').strip("/")
    return ""
