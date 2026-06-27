"""Django REST Framework parser (PRD §9.4) — AST over the project.

Routes from ``urls.py`` ``path(...)`` patterns associated with views; body/response from
DRF serializers; auth from ``permission_classes`` (``IsAuthenticated``). Best-effort:
Django routing is dynamic, so this covers the common ``path('x/', View.as_view())`` and
``ViewSet`` shapes (PRD §9.4).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from postman_mcp.input.parsers.base import iter_source_files, py_field_type, read_text
from postman_mcp.models import (
    BodyField,
    BodyModel,
    InputSource,
    ResponseModel,
    RouteModel,
)

# serializers.CharField() → string, etc.
_SERIALIZER_FIELD_MAP = {
    "CharField": "str", "EmailField": "str", "SlugField": "str", "URLField": "str",
    "UUIDField": "str", "DateTimeField": "str", "DateField": "str",
    "IntegerField": "int", "FloatField": "float", "DecimalField": "float",
    "BooleanField": "bool", "ListField": "list", "DictField": "dict",
}
_VIEW_METHODS = {"get", "post", "put", "patch", "delete"}


def parse(project_root: Path | str) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    serializers: dict[str, BodyModel] = {}
    views: dict[str, dict] = {}
    url_files: list[tuple[Path, ast.Module]] = []
    skipped: list[str] = []

    for path in iter_source_files(root, (".py",)):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            skipped.append(f"{path.name}: {exc.msg}")
            continue
        _collect_serializers(tree, serializers)
        _collect_views(tree, views, serializers)
        if path.name == "urls.py":
            url_files.append((path, tree))

    routes: list[RouteModel] = []
    for path, tree in url_files:
        rel = path.relative_to(root).as_posix()
        for route_path, view_name in _iter_url_patterns(tree):
            view = views.get(view_name)
            methods = view["methods"] if view else ["get"]
            for method in methods:
                routes.append(
                    RouteModel(
                        method=method.upper(),
                        path=route_path,
                        body=view["serializer"] if view and method in ("post", "put", "patch") else None,
                        responses=[
                            ResponseModel(
                                status=201 if method == "post" else 200,
                                body=view["serializer"] if view else None,
                            )
                        ],
                        auth_required=bool(view and view["auth"]),
                        code_ref=rel,
                        source=InputSource.CODE,
                    )
                )
    return routes, skipped


def _collect_serializers(tree: ast.Module, out: dict[str, BodyModel]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            "Serializer" in _base_name(b) for b in node.bases
        ):
            fields: list[BodyField] = []
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                    field_cls = _base_name(stmt.value.func)
                    if field_cls in _SERIALIZER_FIELD_MAP and stmt.targets:
                        tgt = stmt.targets[0]
                        if isinstance(tgt, ast.Name):
                            fields.append(
                                BodyField(
                                    name=tgt.id,
                                    type=py_field_type(_SERIALIZER_FIELD_MAP[field_cls]),
                                )
                            )
            out[node.name] = BodyModel(name=node.name, fields=fields)


def _collect_views(
    tree: ast.Module, out: dict[str, dict], serializers: dict[str, BodyModel]
) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [_base_name(b) for b in node.bases]
        if not any("View" in b or "ViewSet" in b for b in bases):
            continue
        methods: list[str] = []
        serializer: Optional[BodyModel] = None
        auth = False
        is_viewset = any("ViewSet" in b for b in bases)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if stmt.name in _VIEW_METHODS:
                    methods.append(stmt.name)
            if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name):
                tname = stmt.targets[0].id
                if tname == "serializer_class":
                    serializer = serializers.get(_base_name(stmt.value))
                if tname == "permission_classes":
                    auth = "IsAuthenticated" in ast.dump(stmt.value)
        if is_viewset and not methods:
            methods = ["get", "post", "put", "delete"]
        if not methods:
            methods = ["get"]
        out[node.name] = {"methods": methods, "serializer": serializer, "auth": auth}


def _iter_url_patterns(tree: ast.Module):
    """Yield ``(path, view_name)`` from ``path('x/', View.as_view())`` calls."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _base_name(node.func) in ("path", "re_path"):
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            route = node.args[0].value
            if not isinstance(route, str):
                continue
            route = "/" + route.strip("/")
            view_name = ""
            if len(node.args) > 1:
                view_name = _view_name(node.args[1])
            yield route, view_name


def _view_name(node: ast.expr) -> str:
    # View.as_view()  → View
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return _base_name(node.func.value)
        return _base_name(node.func)
    return _base_name(node)


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _base_name(node.func)
    return ""
