"""Express code parser — the most important fallback (no native spec).

Express has no native type system and many real projects never generate an OpenAPI
spec at all, so this parser must stand on its own rather than just "fill gaps" — it is
the most heavily annotated of the four. Body fields are resolved in trust order:

1. **Joi / Zod / Yup schema** validated against ``req.body`` in the route — explicit
   author-declared shape, ``low_confidence=False``.
2. **JSDoc** ``@body {type} name`` tags on the route's doc comment — explicit
   author-declared shape, ``low_confidence=False``.
3. **Destructuring / dot-access** on ``req.body`` — inferred from usage, no type
   information, ``low_confidence=True``.

Auth is detected both per-route (inline middleware) and file-scoped
(``app.use(requireAuth)`` / ``router.use(requireAuth)``), since real apps commonly wire
auth once for the whole router rather than per route.

Everything here is regex/heuristic over ``.js`` / ``.ts`` source — Express has no native
AST tooling this project depends on.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from postman_mcp.input import structural
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

# app.get('/path', mw1, handler)  /  router.post("/x", ...)  /  authRouter.get(...)
# The router variable can be named anything; _route_regex() builds the alternation from
# the express()/Router() definitions actually found in the file (plus app/router as a
# safety net), so routes on arbitrarily-named routers aren't silently missed — and we
# don't match unrelated `.get(`/`.post(` calls (cache.get, db.get, axios.post, ...).
_ROUTE_TEMPLATE = (
    r"""\b(?:{vars})\s*\.\s*(get|post|put|patch|delete)\s*\(\s*['"`]([^'"`]+)['"`]([^)]*)\)"""
)


def _route_regex(text: str) -> "re.Pattern":
    names = structural.express_router_vars(text) | {"app", "router"}
    alt = "|".join(re.escape(v) for v in sorted(names, key=len, reverse=True))
    return re.compile(_ROUTE_TEMPLATE.format(vars=alt), re.IGNORECASE)
_PATH_PARAM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_AUTH_HINTS = ("requireauth", "isauthenticated", "authenticate", "ensureauth", "auth", "protect", "verifytoken")

# File-scoped middleware registration: app.use(requireAuth) / router.use(requireAuth).
# Deliberately excludes `.use('/path', ...)` and `.use(express.json())` — the single
# bare-identifier form is what marks a middleware that runs for every route below it.
_GLOBAL_USE = re.compile(r"\b(?:app|router)\s*\.\s*use\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)")

# req.body.<field> usages give us best-effort body field names.
_DOT_BODY_FIELD = re.compile(r"req\.body\.([A-Za-z_][A-Za-z0-9_]*)")
# const { a, b: renamed, c = default, ...rest } = req.body;
_DESTRUCTURE_BODY = re.compile(r"(?:const|let|var)\s*\{([^{}]*)\}\s*=\s*req\.body\b", re.DOTALL)

_JSDOC_BLOCK = re.compile(r"/\*\*(.*?)\*/", re.DOTALL)
_JSDOC_BODY_TAG = re.compile(r"@body\s+\{(\w+)\}\s+([A-Za-z_][A-Za-z0-9_]*)")
_JSDOC_TYPE_MAP = {
    "number": FieldType.NUMBER,
    "string": FieldType.STRING,
    "boolean": FieldType.BOOLEAN,
    "object": FieldType.OBJECT,
    "array": FieldType.ARRAY,
}

# Joi.object({...}) / z.object({...}) / yup.object({...})
_SCHEMA_OBJECT_CALL = re.compile(r"\b(?:Joi|z|yup)\s*\.\s*object\s*\(")
_SCHEMA_VAR_DEF = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:Joi|z|yup)\s*\.\s*object\s*\("
)
_VALIDATE_CALL = re.compile(r"\.\s*(?:validate|parse)\s*\(")


def parse(
    project_root: Path | str, *, only_files: Optional[list[str]] = None
) -> tuple[list[RouteModel], list[str]]:
    root = Path(project_root)
    files = list(source_files(root, (".js", ".ts", ".mjs", ".cjs"), only_files))
    texts = [(path, read_text(path)) for path in files]

    # Pass 1 — collect validation-schema definitions across the whole project, so a
    # route that references an *imported* schema (the common pattern:
    # ``router.post('/x', validate(employerSchema), handler)`` where ``employerSchema``
    # lives in another file) still resolves to real fields instead of an empty body.
    # On incremental syncs (``only_files`` set) we stay file-local to keep token cost
    # down; the next full sync resolves anything cross-file.
    project_schema_defs: dict[str, list[str]] = {}
    if only_files is None:
        for _, text in texts:
            project_schema_defs.update(_schema_definitions(text))

    # L1 structural pass: the prefix under which each file's router is mounted
    # (``app.use('/api/users', require('./routes'))``) — whole-project, since the mount
    # site lives in a different file than the routes.
    mount_prefixes = structural.build_express(root)

    routes: list[RouteModel] = []
    skipped: list[str] = []
    for path, text in texts:
        rel = path.relative_to(root).as_posix()
        prefix = mount_prefixes.get(rel)
        routes.extend(
            _parse_file(text, rel, project_schema_defs, prefix.prefix if prefix else "")
        )
    return routes, skipped


def _parse_file(
    text: str,
    rel: str,
    project_schema_defs: Optional[dict[str, list[str]]] = None,
    mount_prefix: str = "",
) -> list[RouteModel]:
    matches = list(_route_regex(text).finditer(text))
    global_auth = _has_global_auth_middleware(text)
    # File-local definitions win over project-wide ones of the same name.
    schema_defs = dict(project_schema_defs or {})
    schema_defs.update(_schema_definitions(text))

    routes: list[RouteModel] = []
    for i, match in enumerate(matches):
        method = match.group(1).upper()
        route_path = structural.compose(mount_prefix, match.group(2))
        rest = match.group(3) or ""
        # Bound this route's handler by the next route registration (or EOF) — a
        # reasonable approximation for the flat, sequential style most Express apps use.
        scope_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        handler_text = text[match.end() : scope_end]
        jsdoc = _jsdoc_before(text, match.start())
        routes.append(
            _build_route(method, route_path, rest, handler_text, jsdoc, schema_defs, global_auth, rel)
        )
    return routes


def _has_global_auth_middleware(text: str) -> bool:
    return any(h in name.lower() for name in _GLOBAL_USE.findall(text) for h in _AUTH_HINTS)


def _build_route(
    method: str,
    path: str,
    rest: str,
    handler_text: str,
    jsdoc: str | None,
    schema_defs: dict[str, list[str]],
    global_auth: bool,
    rel: str,
) -> RouteModel:
    path_params = [
        Param(name=name, location=ParamLocation.PATH, required=True)
        for name in _PATH_PARAM.findall(path)
    ]
    auth = global_auth or any(h in rest.lower() for h in _AUTH_HINTS)

    body = None
    if method in ("POST", "PUT", "PATCH"):
        body = _resolve_body(handler_text, rest, jsdoc, schema_defs)

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


def _resolve_body(
    handler_text: str,
    rest: str,
    jsdoc: str | None,
    schema_defs: dict[str, list[str]],
) -> BodyModel:
    """Trust order: validated schema → JSDoc ``@body`` tags → inferred usage.

    Schema detection looks at both the route registration (``rest`` — where validation
    middleware like ``validate(employerSchema)`` lives) and the handler body.
    """
    schema_fields = _schema_body_fields(rest + "\n" + handler_text, schema_defs)
    if schema_fields:
        fields = [BodyField(name=n, required=True) for n in schema_fields]
        return BodyModel(name="RequestBody", fields=fields, low_confidence=False)

    if jsdoc:
        jsdoc_fields = _jsdoc_body_fields(jsdoc)
        if jsdoc_fields:
            return BodyModel(name="RequestBody", fields=jsdoc_fields, low_confidence=False)

    names = list(
        dict.fromkeys(_destructure_field_names(handler_text) + _dot_field_names(handler_text))
    )
    fields = [BodyField(name=n, required=False) for n in names]
    return BodyModel(name="RequestBody", fields=fields, low_confidence=True)


# --- inferred usage (lower confidence) ----------------------------------------------


def _dot_field_names(handler_text: str) -> list[str]:
    seen: list[str] = []
    for name in _DOT_BODY_FIELD.findall(handler_text):
        if name not in seen:
            seen.append(name)
    return seen


def _destructure_field_names(handler_text: str) -> list[str]:
    names: list[str] = []
    for match in _DESTRUCTURE_BODY.finditer(handler_text):
        for part in match.group(1).split(","):
            part = part.strip()
            if not part or part.startswith("..."):
                continue
            key = re.split(r"[:=]", part, maxsplit=1)[0].strip()
            if key and key not in names:
                names.append(key)
    return names


# --- JSDoc @body tags (high confidence) ---------------------------------------------


def _jsdoc_before(text: str, pos: int) -> str | None:
    """The nearest preceding JSDoc block, if only whitespace separates it from ``pos``."""
    best: str | None = None
    for match in _JSDOC_BLOCK.finditer(text):
        if match.end() <= pos and text[match.end() : pos].strip() == "":
            best = match.group(1)
    return best


def _jsdoc_body_fields(jsdoc_text: str) -> list[BodyField]:
    return [
        BodyField(name=name, type=_JSDOC_TYPE_MAP.get(type_str.lower(), FieldType.UNKNOWN), required=True)
        for type_str, name in _JSDOC_BODY_TAG.findall(jsdoc_text)
    ]


# --- Joi / Zod / Yup schemas (high confidence) ---------------------------------------


def _extract_braced(text: str, open_idx: int) -> tuple[str, int]:
    """Depth-aware match from a ``{`` at ``open_idx`` to its closing brace."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i], i + 1
    return text[open_idx + 1 :], len(text)


def _object_keys(obj_text: str) -> list[str]:
    """Top-level keys of an object literal, ignoring nested calls/objects/arrays."""
    segments: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in obj_text:
        if ch in "{[(":
            depth += 1
            current.append(ch)
        elif ch in "}])":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        segments.append("".join(current))

    names: list[str] = []
    for seg in segments:
        match = re.match(r"""^['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?\s*:""", seg.strip())
        if match:
            names.append(match.group(1))
    return names


def _schema_definitions(text: str) -> dict[str, list[str]]:
    """Map ``const NAME = Joi.object({...})``-style schema variables → field names."""
    defs: dict[str, list[str]] = {}
    for match in _SCHEMA_VAR_DEF.finditer(text):
        name = match.group(1)
        brace_idx = text.find("{", match.end())
        if brace_idx == -1:
            continue
        inner, _ = _extract_braced(text, brace_idx)
        defs[name] = _object_keys(inner)
    return defs


def _inline_schema_fields(handler_text: str) -> list[str] | None:
    """Fields from a schema literal defined and validated inline within the handler."""
    for match in _SCHEMA_OBJECT_CALL.finditer(handler_text):
        brace_idx = handler_text.find("{", match.end())
        if brace_idx == -1:
            continue
        inner, end_idx = _extract_braced(handler_text, brace_idx)
        tail = handler_text[end_idx : end_idx + 60]
        if re.match(r"\s*\)\s*" + _VALIDATE_CALL.pattern, tail):
            return _object_keys(inner)
    return None


def _schema_body_fields(text: str, schema_defs: dict[str, list[str]]) -> list[str] | None:
    """Resolve body fields from a validation schema referenced near the route.

    Three forms, in order: an inline ``Joi.object({...}).validate(...)`` literal; a named
    schema called directly (``employerSchema.validate(...)`` / ``.parse(...)``); or a named
    schema handed to validation middleware (``validate(employerSchema)``,
    ``celebrate({ body: employerSchema })``, etc.) — matched by the schema name appearing
    anywhere in the route registration or handler.
    """
    inline = _inline_schema_fields(text)
    if inline:
        return inline
    # Direct .validate()/.parse() on a named schema.
    for name, fields in schema_defs.items():
        if re.search(rf"\b{re.escape(name)}\s*{_VALIDATE_CALL.pattern}", text):
            return fields
    # Named schema passed to a validation middleware/helper.
    for name, fields in schema_defs.items():
        if fields and re.search(rf"\b{re.escape(name)}\b", text):
            return fields
    return None
