"""Django REST Framework parser — AST over the project.

Routes from ``urls.py`` ``path(...)`` patterns associated with views; body/response from
DRF serializers; auth from ``permission_classes`` (``IsAuthenticated``). Best-effort:
Django routing is dynamic, so this covers the common ``path('x/', View.as_view())`` and
``ViewSet`` shapes, plus function-based ``@api_view(['GET', 'POST'])`` views — the other
common DRF pattern, previously invisible to this parser since only class-based views were
collected. A function view's body is inferred from a serializer instantiated inside it
(``PaymentSerializer(data=request.data)``); its auth comes from a
``@permission_classes([IsAuthenticated])`` decorator rather than a class attribute.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from postman_mcp.input.parsers.base import py_field_type, read_text, source_files
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


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    serializers: dict[str, BodyModel] = {}
    views: dict[str, dict] = {}
    url_files: list[tuple[Path, ast.Module]] = []
    skipped: list[str] = []

    for path in source_files(root, (".py",), only_files):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            skipped.append(f"{path.name}: {exc.msg}")
            continue
        _collect_serializers(tree, serializers)
        _collect_views(tree, views, serializers)
        _collect_function_views(tree, views, serializers)
        if path.name == "urls.py":
            url_files.append((path, tree))

    routes: list[RouteModel] = []
    for path, tree in url_files:
        rel = path.relative_to(root).as_posix()
        for route_path, view_name, mapped_methods in _iter_url_patterns(tree):
            view = views.get(view_name)
            # A ViewSet mounted with ``.as_view({'get': 'list', 'post': 'create'})``
            # declares exactly which HTTP methods this URL serves — trust that over the
            # ViewSet's full default method set, so we don't invent PUT/DELETE routes.
            if mapped_methods:
                methods = mapped_methods
            else:
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


def _collect_function_views(
    tree: ast.Module, out: dict[str, dict], serializers: dict[str, BodyModel]
) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        api_view_dec = _api_view_decorator(node)
        if api_view_dec is None:
            continue
        methods = _api_view_methods(api_view_dec) or ["get"]
        out[node.name] = {
            "methods": methods,
            "serializer": _function_serializer(node, serializers),
            "auth": _has_permission_classes_auth(node),
        }


def _api_view_decorator(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[ast.Call]:
    for dec in fn.decorator_list:
        if isinstance(dec, ast.Call) and _base_name(dec.func) == "api_view":
            return dec
    return None


def _api_view_methods(dec: ast.Call) -> list[str]:
    if not dec.args or not isinstance(dec.args[0], (ast.List, ast.Tuple)):
        return []
    return [
        elt.value.lower()
        for elt in dec.args[0].elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    ]


def _function_serializer(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, serializers: dict[str, BodyModel]
) -> Optional[BodyModel]:
    """The first serializer class instantiated anywhere in the view body."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = _base_name(node.func)
            if name in serializers:
                return serializers[name]
    return None


def _has_permission_classes_auth(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in fn.decorator_list:
        if isinstance(dec, ast.Call) and _base_name(dec.func) == "permission_classes":
            if "IsAuthenticated" in ast.dump(dec):
                return True
    return False


def _iter_url_patterns(tree: ast.Module):
    """Yield ``(path, view_name, mapped_methods)`` from ``path('x/', View.as_view())``.

    ``mapped_methods`` is the HTTP-method list from a ViewSet ``.as_view({...})`` mapping
    (e.g. ``['get', 'post']``), or ``[]`` when none is given.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _base_name(node.func) in ("path", "re_path"):
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            route = node.args[0].value
            if not isinstance(route, str):
                continue
            route = "/" + _strip_django_converters(route)
            view_name = ""
            mapped_methods: list[str] = []
            if len(node.args) > 1:
                view_name = _view_name(node.args[1])
                mapped_methods = _as_view_methods(node.args[1])
            yield route, view_name, mapped_methods


def _strip_django_converters(route: str) -> str:
    """``payments/<str:pk>/`` → ``payments/{pk}`` so the path matches the engine's form."""
    route = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)
    return route.strip("/")


def _as_view_methods(node: ast.expr) -> list[str]:
    """HTTP method keys of a ViewSet ``.as_view({'get': 'list', ...})`` mapping."""
    if not (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Dict)):
        return []
    methods: list[str] = []
    for key in node.args[0].keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            methods.append(key.value.lower())
    return methods


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
