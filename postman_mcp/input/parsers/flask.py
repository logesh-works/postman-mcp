"""Flask code parser — routes + blueprint prefix composition.

Routes from ``@app.route('/x', methods=[...])`` / ``@bp.route(...)`` and the Flask 2.0
``@app.get`` / ``@bp.post`` shorthand. Full URLs compose the blueprint's ``url_prefix``
and any ``register_blueprint(url_prefix=...)`` via the structural resolver, so a route
declared on a blueprint mounted under ``/api`` gets the full path — the thing a leaf-only
reader drops.

Flask is untyped, so request bodies are best-effort (inferred from ``request.json`` /
``request.form`` usage) and marked low-confidence; auth is detected from
``@login_required`` / ``@jwt_required``-style decorators.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from postman_mcp.input import structural
from postman_mcp.input.parsers.base import read_text, source_files
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
_PATH_PARAM = re.compile(r"<(?:[^:>]+:)?([^>]+)>")
_AUTH_DECORATORS = (
    "login_required", "jwt_required", "auth_required", "token_required", "requires_auth",
)
# request.json['x'] / request.json.get('x') / request.form[...] / get_json()[...]
_BODY_ACCESS = re.compile(
    r"""(?:request\s*\.\s*(?:json|form)|get_json\(\s*\)|data)\s*"""
    r"""(?:\.\s*get\(\s*['"](\w+)['"]|\[\s*['"](\w+)['"]\s*\])"""
)


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    structure = structural.build_flask(root)
    routes: list[RouteModel] = []
    skipped: list[str] = []
    for path in source_files(root, (".py",), only_files):
        text = read_text(path)
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            skipped.append(f"{path.name}: {exc.msg}")
            continue
        rel = path.relative_to(root).as_posix()
        module, _ = structural.module_name(path.relative_to(root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                routes.extend(_routes_from_function(node, text, rel, module, structure))
    return routes, skipped


def _routes_from_function(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    text: str,
    rel: str,
    module: str,
    structure: "structural.FastApiStructure",
) -> list[RouteModel]:
    routing: list[tuple[list[str], str, str]] = []
    auth = False
    for dec in fn.decorator_list:
        name = (_dec_name(dec) or "").lower()
        if any(a in name for a in _AUTH_DECORATORS):
            auth = True
        info = _routing_decorator(dec)
        if info is not None:
            routing.append(info)
    if not routing:
        return []

    handler_src = ast.get_source_segment(text, fn) or ""
    body_fields = _body_fields(handler_src)
    docstring = ast.get_docstring(fn)

    out: list[RouteModel] = []
    for methods, leaf, var in routing:
        resolved = structure.prefix(module, var)
        path = structural.compose(resolved.prefix, leaf)
        path_params = [
            Param(name=n, location=ParamLocation.PATH, required=True)
            for n in _PATH_PARAM.findall(path)
        ]
        for method in methods:
            body = None
            if method in ("POST", "PUT", "PATCH") and body_fields:
                body = BodyModel(
                    name="RequestBody",
                    fields=[BodyField(name=n, required=False) for n in body_fields],
                    low_confidence=True,
                )
            out.append(
                RouteModel(
                    method=method,
                    path=path,
                    path_params=path_params,
                    body=body,
                    responses=[ResponseModel(status=201 if method == "POST" else 200)],
                    auth_required=auth,
                    docstring=docstring,
                    code_ref=f"{rel}::{fn.name}",
                    source=InputSource.CODE,
                )
            )
    return out


def _routing_decorator(dec: ast.expr) -> Optional[tuple[list[str], str, str]]:
    """Return ``(methods, leaf_path, router_var)`` for a Flask routing decorator."""
    if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
        return None
    attr = dec.func.attr.lower()
    var = dec.func.value.id if isinstance(dec.func.value, ast.Name) else None
    if var is None:
        return None
    if attr == "route":
        if not dec.args or not isinstance(dec.args[0], ast.Constant):
            return None
        if not isinstance(dec.args[0].value, str):
            return None
        return ([m.upper() for m in _methods_kw(dec)] or ["GET"], dec.args[0].value, var)
    if attr in _HTTP:
        if not dec.args or not isinstance(dec.args[0], ast.Constant):
            return None
        if not isinstance(dec.args[0].value, str):
            return None
        return ([attr.upper()], dec.args[0].value, var)
    return None


def _methods_kw(dec: ast.Call) -> list[str]:
    for kw in dec.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
            return [
                e.value
                for e in kw.value.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
    return []


def _dec_name(dec: ast.expr) -> Optional[str]:
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Call):
        return _dec_name(dec.func)
    return None


def _body_fields(src: str) -> list[str]:
    names: list[str] = []
    for a, b in _BODY_ACCESS.findall(src):
        name = a or b
        if name and name not in names:
            names.append(name)
    return names
