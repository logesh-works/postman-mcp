"""FastAPI code parser — used when no OpenAPI spec is available.

Extracts routes from ``@app.post("/path")`` / ``@router.get(...)`` decorators, body and
response shapes from Pydantic models, auth from ``Depends(get_current_user)``, and
declared headers from ``Header(...)`` defaults (required iff the default is ``...``).

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

from postman_mcp.input import structural
from postman_mcp.input.parsers.base import (
    py_field_type,
    read_text,
    source_files,
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


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    """Parse a FastAPI project into route models.

    ``only_files``, when given, restricts the scan to those files (incremental syncs)
    instead of walking the whole project.
    """
    root = Path(project_root)
    models: dict[str, BodyModel] = {}
    files: list[tuple[Path, ast.Module]] = []
    skipped: list[str] = []

    # L1 structural pass: resolve the mount graph across the WHOLE project so a route's
    # full prefix (APIRouter(prefix=...) + include_router(prefix=...), possibly in another
    # file like main.py) is composed correctly rather than dropped.
    structure = structural.build_fastapi(root)

    # Pass 1: collect Pydantic models + parse all files once.
    for path in source_files(root, (".py",), only_files):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            skipped.append(f"{path.name}: {exc.msg}")
            continue
        files.append((path, tree))
        _collect_models(tree, models)

    # Pass 2: extract routes, composing each leaf path with its resolved prefix.
    routes: list[RouteModel] = []
    for path, tree in files:
        rel = path.relative_to(root).as_posix()
        module, _ = structural.module_name(path.relative_to(root))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                routes.extend(
                    _route_from_function(node, models, rel, structure, module)
                )
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
    structure: "structural.FastApiStructure",
    module: str,
) -> list[RouteModel]:
    """Build a route per resolved mount prefix (>1 only for versioned multi-mounts)."""
    for dec in fn.decorator_list:
        info = _decorator_route(dec)
        if info is None:
            continue
        method, leaf_path, response_model, router_var = info
        leaf_param_names = set(_PATH_PARAM.findall(leaf_path))

        arg_path_params: dict[str, Param] = {}
        query_params: list[Param] = []
        headers: list[Param] = []
        body: Optional[BodyModel] = None
        auth = False

        for arg, default in _iter_args(fn):
            ann = _annotation_name(arg.annotation) if arg.annotation else ""
            if _is_auth_default(default):
                auth = True
                continue
            if _is_header_default(default):
                headers.append(
                    Param(
                        name=_header_name(arg.arg),
                        location=ParamLocation.HEADER,
                        type=py_field_type(ann),
                        required=_header_is_required(default),
                    )
                )
                continue
            if arg.arg in leaf_param_names:
                arg_path_params[arg.arg] = Param(
                    name=arg.arg,
                    location=ParamLocation.PATH,
                    type=py_field_type(ann),
                    required=True,
                )
            elif ann in models:
                body = models[ann]
            else:
                # Query param — unwrap Optional[X]/Annotated[X,...]/Union[X,None] so a
                # ``page: Optional[int] = None`` is still recognized as an int query.
                scalar = _query_scalar(arg.annotation)
                if scalar.lower() in {"str", "int", "float", "bool"}:
                    query_params.append(
                        Param(
                            name=arg.arg,
                            location=ParamLocation.QUERY,
                            type=py_field_type(scalar),
                            required=default is None,
                        )
                    )

        success = 201 if method == "POST" else 200
        responses = [
            ResponseModel(
                status=success,
                body=models.get(response_model) if response_model else None,
            )
        ]

        out: list[RouteModel] = []
        for resolved in structure.prefixes(module, router_var):
            full = structural.compose(resolved.prefix, leaf_path)
            path_params = [
                arg_path_params.get(
                    name, Param(name=name, location=ParamLocation.PATH, required=True)
                )
                for name in _PATH_PARAM.findall(full)
            ]
            out.append(
                RouteModel(
                    method=method,
                    path=full,
                    path_params=path_params,
                    query_params=query_params,
                    headers=headers,
                    body=body,
                    responses=responses,
                    auth_required=auth,
                    docstring=ast.get_docstring(fn),
                    code_ref=f"{rel}::{fn.name}",
                    source=InputSource.CODE,
                )
            )
        return out
    return []


def _decorator_route(dec: ast.expr) -> Optional[tuple[str, str, Optional[str], str]]:
    """Return ``(METHOD, leaf_path, response_model, router_var)`` for a routing decorator.

    ``router_var`` is the object the decorator hangs off (``app`` in ``@app.post``,
    ``router`` in ``@router.get``) — the key the structural resolver uses to look up the
    full mount-chain prefix for this route.
    """
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute) or func.attr.lower() not in _HTTP:
        return None
    method = func.attr.upper()
    router_var = _annotation_name(func.value)
    path = None
    if dec.args and isinstance(dec.args[0], ast.Constant):
        path = dec.args[0].value
    if not isinstance(path, str):
        return None
    response_model = None
    for kw in dec.keywords:
        if kw.arg == "response_model":
            response_model = _annotation_name(kw.value)
    return method, path, response_model, router_var


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


def _is_header_default(default: Optional[ast.expr]) -> bool:
    return isinstance(default, ast.Call) and _annotation_name(default.func) == "Header"


def _header_is_required(default: ast.Call) -> bool:
    """``Header(...)`` (Ellipsis) is required; any concrete default value is not."""
    if default.args and isinstance(default.args[0], ast.Constant):
        return default.args[0].value is Ellipsis
    for kw in default.keywords:
        if kw.arg == "default":
            return isinstance(kw.value, ast.Constant) and kw.value.value is Ellipsis
    return not default.args and not default.keywords


def _header_name(arg_name: str) -> str:
    """FastAPI's default conversion: ``x_api_key`` -> ``X-Api-Key``."""
    return "-".join(part.capitalize() for part in arg_name.split("_"))


def _query_scalar(annotation: Optional[ast.expr]) -> str:
    """Effective scalar type, unwrapping ``Optional[X]`` / ``Annotated[X, ...]`` / ``Union``."""
    if annotation is None:
        return ""
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Subscript):
        base = _annotation_name(annotation.value)
        sl = annotation.slice
        elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
        if base == "Optional":
            return _query_scalar(elts[0]) if elts else ""
        if base == "Annotated":
            return _query_scalar(elts[0]) if elts else ""
        if base == "Union":
            for e in elts:
                s = _query_scalar(e)
                if s.lower() in {"str", "int", "float", "bool"}:
                    return s
            return ""
        return ""  # List[X], Dict[...], etc. — not a scalar query param
    return ""


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
