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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from postman_mcp.input import structural
from postman_mcp.input.parsers.base import py_field_type, read_text, source_files
from postman_mcp.models import (
    BodyField,
    BodyModel,
    InputSource,
    Param,
    ParamLocation,
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

# DRF router: a registered ViewSet generates standard routes from its action methods.
_DRF_ACTIONS = {"list", "create", "retrieve", "update", "partial_update", "destroy"}
# action -> (slot, http_method); "collection" = /prefix, "detail" = /prefix/{pk}
_DRF_ACTION_ROUTE = {
    "list": ("collection", "get"),
    "create": ("collection", "post"),
    "retrieve": ("detail", "get"),
    "update": ("detail", "put"),
    "partial_update": ("detail", "patch"),
    "destroy": ("detail", "delete"),
}
_DRF_ROUTER_FACTORIES = ("DefaultRouter", "SimpleRouter")
_PATH_PARAM_NAME = re.compile(r"\{(\w+)\}")


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    serializers: dict[str, BodyModel] = {}
    views: dict[str, dict] = {}
    url_modules: dict[str, _UrlModule] = {}
    skipped: list[str] = []

    # Always scan the whole project for serializers/views/url graph: an included
    # ``urls.py`` and the views it routes to live in different files, and the prefix that
    # mounts it (``path('api/', include('app.urls'))``) lives in yet another. only_files
    # would break cross-file include composition, so the structural graph is whole-project.
    for path in source_files(root, (".py",), None):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            skipped.append(f"{path.name}: {exc.msg}")
            continue
        _collect_serializers(tree, serializers)
        _collect_views(tree, views, serializers)
        _collect_function_views(tree, views, serializers)
        if path.name == "urls.py":
            module, _ = structural.module_name(path.relative_to(root))
            url_modules[module] = _collect_url_module(
                tree, module, path.relative_to(root).as_posix()
            )

    viewset_actions = {
        name: v["actions"] for name, v in views.items() if v.get("actions")
    }

    routes: list[RouteModel] = []
    for route_path, view_name, mapped_methods, rel in _compose_url_patterns(
        url_modules, viewset_actions
    ):
        view = views.get(view_name)
        # A ViewSet mounted with ``.as_view({'get': 'list', 'post': 'create'})``
        # declares exactly which HTTP methods this URL serves — trust that over the
        # ViewSet's full default method set, so we don't invent PUT/DELETE routes.
        if mapped_methods:
            methods = mapped_methods
        else:
            methods = view["methods"] if view else ["get"]
        path_params = [
            Param(name=n, location=ParamLocation.PATH, required=True)
            for n in _PATH_PARAM_NAME.findall(route_path)
        ]
        for method in methods:
            routes.append(
                RouteModel(
                    method=method.upper(),
                    path=route_path,
                    path_params=path_params,
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
        actions: set[str] = set()
        serializer: Optional[BodyModel] = None
        auth = False
        is_viewset = any("ViewSet" in b for b in bases)
        is_model_viewset = any("ModelViewSet" in b for b in bases)
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if stmt.name in _VIEW_METHODS:
                    methods.append(stmt.name)
                if stmt.name in _DRF_ACTIONS:
                    actions.add(stmt.name)
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
        # A ModelViewSet provides the full standard action set even without explicit defs.
        if is_model_viewset:
            actions = set(_DRF_ACTIONS)
        out[node.name] = {
            "methods": methods,
            "serializer": serializer,
            "auth": auth,
            "actions": actions,
        }


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


@dataclass
class _UrlLeaf:
    route: str  # raw Django route string (converters intact), e.g. "payments/<str:pk>/"
    view_name: str
    mapped_methods: list  # from ViewSet .as_view({...}), else []


@dataclass
class _UrlInclude:
    route: str  # the prefix this include is mounted under
    target_module: Optional[str]  # "app.urls" from include('app.urls'); None if dynamic


@dataclass
class _UrlModule:
    module: str
    rel: str
    leaves: list  # list[_UrlLeaf]
    includes: list  # list[_UrlInclude]
    # DRF routers: var -> list of (prefix, viewset_name) from router.register(...)
    routers: dict
    # (mount_prefix, router_var) from path('p/', include(router.urls)) / urlpatterns = router.urls
    router_includes: list


def _collect_url_module(tree: ast.Module, module: str, rel: str) -> _UrlModule:
    """Split a ``urls.py`` into leaf routes, ``include(...)`` mounts, and DRF routers.

    Distinguishing these is the whole point: an ``include('app.urls')`` carries a *prefix*
    that must compose onto every route in the included module, and a DRF
    ``router.register('users', UserViewSet)`` expands into the full standard route set —
    both things the old leaf-only reader dropped.
    """
    leaves: list[_UrlLeaf] = []
    includes: list[_UrlInclude] = []
    routers: dict = {}
    router_includes: list = []

    for node in ast.walk(tree):
        # DRF router definitions and .register() calls
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if _base_name(node.value.func) in _DRF_ROUTER_FACTORIES:
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        routers.setdefault(tgt.id, [])
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
            and isinstance(node.func.value, ast.Name)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            viewset = _view_name(node.args[1]) if len(node.args) > 1 else ""
            routers.setdefault(node.func.value.id, []).append(
                (node.args[0].value, viewset)
            )
        # urlpatterns = router.urls  /  urlpatterns += router.urls  (mount at root)
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            rv = _router_urls_ref(node.value)
            if rv is not None:
                router_includes.append(("", rv))

        # path()/re_path() entries: leaf, module include, or router include
        if isinstance(node, ast.Call) and _base_name(node.func) in ("path", "re_path"):
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            route = node.args[0].value
            if not isinstance(route, str):
                continue
            target = node.args[1] if len(node.args) > 1 else None
            router_var = _router_include_ref(target)
            if router_var is not None:
                router_includes.append((route, router_var))
                continue
            inc_module = _include_target(target)
            if inc_module is not _NOT_INCLUDE:
                includes.append(_UrlInclude(route=route, target_module=inc_module))
            else:
                leaves.append(
                    _UrlLeaf(
                        route=route,
                        view_name=_view_name(target) if target is not None else "",
                        mapped_methods=_as_view_methods(target) if target is not None else [],
                    )
                )
    return _UrlModule(
        module=module, rel=rel, leaves=leaves, includes=includes,
        routers=routers, router_includes=router_includes,
    )


def _router_urls_ref(node: Optional[ast.expr]) -> Optional[str]:
    """``router.urls`` → ``"router"`` for a direct ``urlpatterns = router.urls``."""
    if isinstance(node, ast.Attribute) and node.attr == "urls" and isinstance(
        node.value, ast.Name
    ):
        return node.value.id
    return None


def _router_include_ref(node: Optional[ast.expr]) -> Optional[str]:
    """``include(router.urls)`` → ``"router"``; else None."""
    if isinstance(node, ast.Call) and _base_name(node.func) == "include":
        if node.args:
            return _router_urls_ref(node.args[0])
    return None


# sentinel so "not an include" is distinguishable from "include with unresolved target"
_NOT_INCLUDE = object()


def _include_target(node: Optional[ast.expr]):
    """``include('app.urls')`` → ``"app.urls"``; ``include(other)`` → None; else sentinel."""
    if not (isinstance(node, ast.Call) and _base_name(node.func) == "include"):
        return _NOT_INCLUDE
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
        node.args[0].value, str
    ):
        return node.args[0].value  # "app.urls"
    return None  # include((patterns, app_name)) / include(var) — dynamic, unresolved


def _dj_join(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts if p.strip("/"))


def _compose_url_patterns(modules: dict, viewset_actions: Optional[dict] = None):
    """Walk the include graph from each root, composing prefixes onto leaf routes.

    Yields ``(normalized_path, view_name, mapped_methods, rel)``. Modules that are
    ``include``d by another are not walked as roots, so their routes appear exactly once,
    with the full mounted prefix. DRF ``router.register`` entries are expanded into the
    standard collection/detail routes for each viewset action.
    """
    viewset_actions = viewset_actions or {}
    included = {
        inc.target_module
        for mod in modules.values()
        for inc in mod.includes
        if inc.target_module
    }
    roots = [m for m in modules.values() if m.module not in included]
    # Fallback: if every module is included (no clear root, e.g. cyclic), treat all as
    # roots so nothing is silently dropped.
    if not roots:
        roots = list(modules.values())

    seen: set = set()

    def emit(path: str, view_name: str, methods: list, rel: str):
        key = (path, view_name, tuple(methods), rel)
        if key in seen:
            return
        seen.add(key)
        return (path, view_name, methods, rel)

    def walk(mod: _UrlModule, prefix: str, stack: frozenset):
        for leaf in mod.leaves:
            path = "/" + _strip_django_converters(_dj_join(prefix, leaf.route))
            row = emit(path, leaf.view_name, leaf.mapped_methods, mod.rel)
            if row:
                yield row
        # DRF routers registered in this module, mounted via include(router.urls)
        for mount_prefix, router_var in mod.router_includes:
            for reg_prefix, viewset in mod.routers.get(router_var, []):
                coll = "/" + _strip_django_converters(_dj_join(prefix, mount_prefix, reg_prefix))
                detail = "/" + _strip_django_converters(
                    _dj_join(prefix, mount_prefix, reg_prefix, "<pk>")
                )
                for action in viewset_actions.get(viewset, set()):
                    slot, method = _DRF_ACTION_ROUTE[action]
                    path = coll if slot == "collection" else detail
                    row = emit(path, viewset, [method], mod.rel)
                    if row:
                        yield row
        for inc in mod.includes:
            child = modules.get(inc.target_module) if inc.target_module else None
            if child is not None and inc.target_module not in stack:
                yield from walk(child, _dj_join(prefix, inc.route), stack | {inc.target_module})

    for root in roots:
        yield from walk(root, "", frozenset())


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
