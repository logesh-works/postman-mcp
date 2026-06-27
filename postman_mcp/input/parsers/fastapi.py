"""FastAPI code parser — used when no OpenAPI spec is available.

Extracts routes from ``@app.post("/path")`` / ``@router.get(...)`` decorators, body and
response shapes from Pydantic models, and auth from ``Depends(get_current_user)``.

Pydantic v1 vs v2: model fields are read **statically from the AST** (both versions use
``name: type`` annotations), so this parser is version-agnostic and needs no import of
project code. When FastAPI serves OpenAPI (Path A) this parser is moot — the spec already
carries resolved schemas.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from postman_mcp.input.parsers.base import (
    iter_source_files,
    py_field_type,
    read_text,
)
from postman_mcp.models import (
    BodyField,
    BodyModel,
    InputSource,
    Param,
    ParamLocation,
    ResponseModel,
    RouteModel,
)

_HTTP = {"get", "post", "put", "patch", "delete", "head", "options"}
_PATH_PARAM = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")
_AUTH_HINTS = ("get_current_user", "current_user", "require_auth", "auth", "verify_token")


def parse(project_root: Path | str) -> tuple[list[RouteModel], list[str]]:
    """Parse a FastAPI project into route models."""
    root = Path(project_root)
    models: dict[str, BodyModel] = {}
    files: list[tuple[Path, ast.Module]] = []
    skipped: list[str] = []

    # Pass 1: collect Pydantic models + parse all files once.
    for path in iter_source_files(root, (".py",)):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            skipped.append(f"{path.name}: {exc.msg}")
            continue
        files.append((path, tree))
        _collect_models(tree, models)

    # Pass 2: extract routes.
    routes: list[RouteModel] = []
    for path, tree in files:
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                route = _route_from_function(node, models, rel)
                if route is not None:
                    routes.append(route)
    return routes, skipped


def _collect_models(tree: ast.Module, models: dict[str, BodyModel]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _looks_like_model(node):
            fields: list[BodyField] = []
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.append(
                        BodyField(
                            name=stmt.target.id,
                            type=py_field_type(_annotation_name(stmt.annotation)),
                            required=stmt.value is None,
                        )
                    )
            models[node.name] = BodyModel(name=node.name, fields=fields)


def _looks_like_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = _annotation_name(base)
        if "BaseModel" in name or "Schema" in name:
            return True
    return False


def _route_from_function(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    models: dict[str, BodyModel],
    rel: str,
) -> Optional[RouteModel]:
    for dec in fn.decorator_list:
        info = _decorator_route(dec)
        if info is None:
            continue
        method, path, response_model = info
        path_param_names = _PATH_PARAM.findall(path)

        path_params: list[Param] = []
        query_params: list[Param] = []
        body: Optional[BodyModel] = None
        auth = False

        for arg, default in _iter_args(fn):
            ann = _annotation_name(arg.annotation) if arg.annotation else ""
            if _is_auth_default(default):
                auth = True
                continue
            if arg.arg in path_param_names:
                path_params.append(
                    Param(
                        name=arg.arg,
                        location=ParamLocation.PATH,
                        type=py_field_type(ann),
                        required=True,
                    )
                )
            elif ann in models:
                body = models[ann]
            elif ann and ann.lower() in {"str", "int", "float", "bool"}:
                query_params.append(
                    Param(
                        name=arg.arg,
                        location=ParamLocation.QUERY,
                        type=py_field_type(ann),
                        required=default is None,
                    )
                )

        responses: list[ResponseModel] = []
        success = 201 if method == "POST" else 200
        responses.append(
            ResponseModel(
                status=success,
                body=models.get(response_model) if response_model else None,
            )
        )

        return RouteModel(
            method=method,
            path=path,
            path_params=path_params,
            query_params=query_params,
            body=body,
            responses=responses,
            auth_required=auth,
            docstring=ast.get_docstring(fn),
            code_ref=f"{rel}::{fn.name}",
            source=InputSource.CODE,
        )
    return None


def _decorator_route(dec: ast.expr) -> Optional[tuple[str, str, Optional[str]]]:
    """Return ``(METHOD, path, response_model)`` for a routing decorator, else None."""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute) or func.attr.lower() not in _HTTP:
        return None
    method = func.attr.upper()
    path = None
    if dec.args and isinstance(dec.args[0], ast.Constant):
        path = dec.args[0].value
    if not isinstance(path, str):
        return None
    response_model = None
    for kw in dec.keywords:
        if kw.arg == "response_model":
            response_model = _annotation_name(kw.value)
    return method, path, response_model


def _iter_args(fn: ast.FunctionDef | ast.AsyncFunctionDef):
    """Yield ``(arg, default_or_None)`` for positional+kw args."""
    args = fn.args
    posonly = getattr(args, "posonlyargs", [])
    all_args = [*posonly, *args.args]
    defaults = list(args.defaults)
    pad = [None] * (len(all_args) - len(defaults))
    for arg, default in zip(all_args, pad + defaults):
        if arg.arg in ("self", "cls"):
            continue
        yield arg, default
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        yield arg, default


def _is_auth_default(default: Optional[ast.expr]) -> bool:
    if default is None:
        return False
    if isinstance(default, ast.Call):
        name = _annotation_name(default.func)
        if name in ("Depends", "Security"):
            inner = _annotation_name(default.args[0]) if default.args else ""
            return any(h in inner.lower() for h in _AUTH_HINTS)
    return False


def _annotation_name(node: Optional[ast.expr]) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):  # Optional[X], List[X]
        return _annotation_name(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""
