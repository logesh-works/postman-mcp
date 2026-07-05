"""L1 structural resolver — deterministic full-URL composition.

Route URLs are a *graph composition* problem, not a per-file extraction problem: the full
path is the concatenation of prefixes along a mount chain scattered across files
(``APIRouter(prefix=...)`` + ``app.include_router(child, prefix=...)``). Reading the leaf
decorator alone — which is what the old parser did — drops every prefix and produces
wrong URLs.

This module builds the mount graph across the whole project, follows imports to resolve
mount targets cross-file, and answers one question per router variable: **what full
prefix applies to routes declared on it?** It is pure structure (deterministic), never
semantics. When a mount can't be resolved (dynamic import, cross-package boundary,
computed prefix) the router is reported ``resolved=False`` — a *known unknown*, never a
silent wrong answer.

Implemented for FastAPI (``build_fastapi``), Flask (``build_flask``, same graph model —
``APIRouter``/``include_router`` and ``Blueprint``/``register_blueprint`` are the same
shape), and Express (``build_express``, a separate regex-based per-file resolver since
there's no Python-accessible JS/TS AST here). Django's ``include()`` chain and Spring's
class-level ``@RequestMapping`` are resolved directly inside their own parsers instead —
neither needs a separate graph pass.
"""

from __future__ import annotations

import ast
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from postman_mcp.input.parsers.base import read_text, source_files

_ROUTER_FACTORIES = ("APIRouter", "FastAPI")


# --- public result types ------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedPrefix:
    """The full prefix applying to routes on a router, plus whether we could confirm it.

    ``resolved=False`` means the router is defined but we could not trace it to an app
    root (never mounted, or mounted via an unresolvable reference) — the prefix is
    best-effort (its own ``prefix=`` only) and should be treated as lower confidence.
    """

    prefix: str
    resolved: bool


# --- normalization helpers ----------------------------------------------------------


def _norm(prefix: Optional[str]) -> str:
    p = (prefix or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def _join(*parts: str) -> str:
    return "".join(_norm(p) for p in parts)


def compose(prefix: str, leaf: str) -> str:
    """Join a resolved prefix with a leaf decorator path into a full route path."""
    prefix = _norm(prefix)
    leaf = (leaf or "").strip()
    if not prefix:
        return leaf if leaf.startswith("/") else "/" + leaf
    if not leaf or leaf == "/":
        return prefix or "/"
    if not leaf.startswith("/"):
        leaf = "/" + leaf
    return prefix + leaf


def module_name(rel: Path) -> tuple[str, bool]:
    """``app/routers/users.py`` → ``("app.routers.users", False)``;
    ``app/routers/__init__.py`` → ``("app.routers", True)``."""
    parts = list(rel.with_suffix("").parts)
    is_package = bool(parts) and parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def _parent(module: str) -> str:
    return module.rsplit(".", 1)[0] if "." in module else ""


# --- per-module collected structure -------------------------------------------------


@dataclass
class _RouterDef:
    module: str
    var: str
    own_prefix: str
    is_app: bool


@dataclass
class _RawMount:
    module: str
    parent_node: ast.expr
    child_node: Optional[ast.expr]
    prefix: str


@dataclass
class _ModuleInfo:
    module: str
    is_package: bool
    # localname -> ("module", dotted) | ("from", base_module, original_name)
    imports: dict
    routers: dict  # var -> _RouterDef
    mounts: list  # list[_RawMount]


# --- AST extraction -----------------------------------------------------------------


def _callee_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _kw_str(call: ast.Call, name: str) -> Optional[str]:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(
            kw.value.value, str
        ):
            return kw.value.value
    return None


def _resolve_relative(module: str, is_package: bool, level: int, mod_part: Optional[str]) -> str:
    pkg = module if is_package else _parent(module)
    base = pkg
    for _ in range(level - 1):
        base = _parent(base)
    if mod_part:
        base = f"{base}.{mod_part}" if base else mod_part
    return base


def _collect_imports(tree: ast.Module, module: str, is_package: bool) -> dict:
    imports: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    imports[alias.asname] = ("module", alias.name)
                else:
                    # `import a.b.c` binds the top name `a`; map it to the top package.
                    top = alias.name.split(".")[0]
                    imports[top] = ("module", top)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = _resolve_relative(module, is_package, node.level, node.module)
            else:
                base = node.module or ""
            for alias in node.names:
                local = alias.asname or alias.name
                imports[local] = ("from", base, alias.name)
    return imports


def _collect_module(path: Path, root: Path) -> Optional[_ModuleInfo]:
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return None
    module, is_package = module_name(path.relative_to(root))
    imports = _collect_imports(tree, module, is_package)
    routers: dict = {}
    mounts: list = []

    for node in ast.walk(tree):
        # router/app definitions: `name = APIRouter(prefix="...")` / `app = FastAPI()`
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            callee = _callee_name(node.value.func)
            if callee in _ROUTER_FACTORIES:
                own_prefix = _norm(_kw_str(node.value, "prefix"))
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        routers[tgt.id] = _RouterDef(
                            module, tgt.id, own_prefix, callee == "FastAPI"
                        )
        # mounts: `<parent>.include_router(<child>, prefix="...")`
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
        ):
            child = node.args[0] if node.args else None
            mounts.append(
                _RawMount(
                    module=module,
                    parent_node=node.func.value,
                    child_node=child,
                    prefix=_norm(_kw_str(node, "prefix")),
                )
            )
    return _ModuleInfo(module, is_package, imports, routers, mounts)


# --- reference resolution (follow imports to a (module, var) key) --------------------


def _resolve_module(node: ast.expr, info: _ModuleInfo, modules: set) -> Optional[str]:
    """Resolve an expression that names a *module* (e.g. ``users`` in ``users.router``)."""
    if isinstance(node, ast.Name):
        binding = info.imports.get(node.id)
        if not binding:
            return None
        if binding[0] == "module":
            return binding[1] if binding[1] in modules else None
        if binding[0] == "from":
            _, base, orig = binding
            full = f"{base}.{orig}" if base else orig
            return full if full in modules else None
        return None
    if isinstance(node, ast.Attribute):
        parent_mod = _resolve_module(node.value, info, modules)
        if parent_mod:
            cand = f"{parent_mod}.{node.attr}"
            if cand in modules:
                return cand
    return None


def _resolve_ref(
    node: Optional[ast.expr], info: _ModuleInfo, modules: set
) -> Optional[tuple]:
    """Resolve an ``include_router`` argument (or parent) to a ``(module, var)`` key."""
    if node is None:
        return None
    if isinstance(node, ast.Name):
        name = node.id
        if name in info.routers:  # router defined locally
            return (info.module, name)
        binding = info.imports.get(name)
        if not binding:
            return None
        if binding[0] == "from":
            _, base, orig = binding
            full = f"{base}.{orig}" if base else orig
            if full in modules:
                return None  # it's a module, not a router variable
            return (base, orig)  # `from .users import router as r` → (..users, router)
        return None  # plain module alias used as a router → unresolved
    if isinstance(node, ast.Attribute):  # `users.router`
        base_mod = _resolve_module(node.value, info, modules)
        if base_mod is not None:
            return (base_mod, node.attr)
    return None


# --- the structure object -----------------------------------------------------------


class FastApiStructure:
    """Resolved mount graph for a FastAPI project; answers prefix-per-router queries."""

    def __init__(self, registry: dict, mounts: list) -> None:
        self._registry = registry  # (module, var) -> _RouterDef
        self._mounts = mounts  # list[(parent_key, child_key, prefix)]
        self._memo: dict = {}

    def prefix(self, module: str, var: str) -> ResolvedPrefix:
        return self._resolve((module, var), frozenset())

    def prefixes(self, module: str, var: str) -> list:
        """All distinct mount-chain prefixes for a router.

        A router mounted under several prefixes (e.g. ``include_router(r, prefix="/v1")``
        *and* ``prefix="/v2")`` for API versioning) yields one entry per mount, so the
        parser can emit the route under each version. Single-mount routers return one.
        """
        results = self._resolve_all((module, var), frozenset())
        seen: dict = {}
        for r in results:
            seen.setdefault(r.prefix, r)
        return list(seen.values())

    def _resolve_all(self, key: tuple, stack: frozenset) -> list:
        rd = self._registry.get(key)
        if rd is None:
            return [ResolvedPrefix("", False)]
        if rd.is_app:
            return [ResolvedPrefix(rd.own_prefix, True)]
        parents = [m for m in self._mounts if m[1] == key]
        if not parents or key in stack:
            return [ResolvedPrefix(rd.own_prefix, False)]
        out: list = []
        for parent_key, _child, mount_prefix in parents:
            for pres in self._resolve_all(parent_key, stack | {key}):
                out.append(
                    ResolvedPrefix(
                        _join(pres.prefix, mount_prefix, rd.own_prefix), pres.resolved
                    )
                )
        return out or [ResolvedPrefix(rd.own_prefix, False)]

    def _resolve(self, key: tuple, stack: frozenset) -> ResolvedPrefix:
        if key in self._memo:
            return self._memo[key]
        rd = self._registry.get(key)
        if rd is None:
            return ResolvedPrefix("", False)  # unknown router var → no prefix, unresolved
        if rd.is_app:
            res = ResolvedPrefix(rd.own_prefix, True)
            self._memo[key] = res
            return res
        parents = [m for m in self._mounts if m[1] == key]
        if not parents:
            res = ResolvedPrefix(rd.own_prefix, False)  # orphan: defined, never mounted
        elif key in stack:
            res = ResolvedPrefix(rd.own_prefix, False)  # cycle guard
        else:
            parent_key, _child, mount_prefix = parents[0]
            pres = self._resolve(parent_key, stack | {key})
            res = ResolvedPrefix(
                _join(pres.prefix, mount_prefix, rd.own_prefix), pres.resolved
            )
        self._memo[key] = res
        return res


def _assemble(infos: list) -> FastApiStructure:
    """Shared graph assembly: collected module infos → resolved prefix structure.

    Used by both FastAPI (APIRouter/include_router) and Flask (Blueprint/
    register_blueprint), which share the same mount-graph shape.
    """
    modules = {info.module for info in infos}
    registry: dict = {}
    for info in infos:
        for var, rd in info.routers.items():
            registry[(info.module, var)] = rd

    mounts: list = []
    for info in infos:
        for raw in info.mounts:
            parent_key = _resolve_ref(raw.parent_node, info, modules)
            child_key = _resolve_ref(raw.child_node, info, modules)
            if parent_key is not None and child_key is not None:
                mounts.append((parent_key, child_key, raw.prefix))

    return FastApiStructure(registry, mounts)


def build_fastapi(project_root: Path | str) -> FastApiStructure:
    """Scan the whole project and resolve the FastAPI mount graph.

    Always scans the full project (not an incremental subset): a route's prefix can live
    in a file the route file doesn't import directly (e.g. ``main.py``'s
    ``include_router``), so the graph must be whole-project to be correct.
    """
    root = Path(project_root)
    infos = [
        info
        for path in source_files(root, (".py",), None)
        if (info := _collect_module(path, root)) is not None
    ]
    return _assemble(infos)


# --- Flask --------------------------------------------------------------------------
#
# Flask blueprints mirror FastAPI routers: ``bp = Blueprint('x', __name__,
# url_prefix='/api')`` defines a prefix, ``app.register_blueprint(bp, url_prefix='/v1')``
# mounts it. We reuse the same graph machinery.

_FLASK_FACTORIES = ("Blueprint", "Flask")


def _collect_module_flask(path: Path, root: Path):
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return None
    module, is_package = module_name(path.relative_to(root))
    imports = _collect_imports(tree, module, is_package)
    routers: dict = {}
    mounts: list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            callee = _callee_name(node.value.func)
            if callee == "Blueprint":
                own_prefix = _norm(_kw_str(node.value, "url_prefix"))
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        routers[tgt.id] = _RouterDef(module, tgt.id, own_prefix, False)
            elif callee == "Flask":
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        routers[tgt.id] = _RouterDef(module, tgt.id, "", True)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register_blueprint"
        ):
            child = node.args[0] if node.args else None
            mounts.append(
                _RawMount(
                    module=module,
                    parent_node=node.func.value,
                    child_node=child,
                    prefix=_norm(_kw_str(node, "url_prefix")),
                )
            )
    return _ModuleInfo(module, is_package, imports, routers, mounts)


def build_flask(project_root: Path | str) -> FastApiStructure:
    """Resolve the Flask blueprint mount graph across the whole project."""
    root = Path(project_root)
    infos = [
        info
        for path in source_files(root, (".py",), None)
        if (info := _collect_module_flask(path, root)) is not None
    ]
    return _assemble(infos)


# --- Express ------------------------------------------------------------------------
#
# Express mounts a router under a prefix at the *registration* site, usually in another
# file: ``app.use('/api/users', require('./routes/users'))``. The router's own routes
# (``router.get('/:id')``) must inherit that prefix. We resolve, per file, the full
# prefix under which that file's exported router is mounted, then the parser prepends it.

_EX_ROUTER_DEF = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*=\s*(express\s*\(\s*\)|express\s*\.\s*Router\s*\(\s*\)|Router\s*\(\s*\))"
)
_EX_EXPORT = re.compile(r"module\.exports\s*=\s*(\w+)|export\s+default\s+(\w+)")
_EX_REQUIRE = re.compile(
    r"(?:const|let|var)\s+(\w+)\s*=\s*require\(\s*['\"`]([^'\"`]+)['\"`]\s*\)"
)
_EX_IMPORT = re.compile(r"import\s+(\w+)\s+from\s+['\"`]([^'\"`]+)['\"`]")
# parent.use('/prefix', child)
_EX_MOUNT = re.compile(
    r"(\w+)\s*\.\s*use\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*,\s*(\w+)\s*\)"
)
# parent.use('/prefix', require('./mod'))  — the very common inline-require mount
_EX_MOUNT_REQUIRE = re.compile(
    r"(\w+)\s*\.\s*use\s*\(\s*['\"`]([^'\"`]+)['\"`]\s*,\s*require\(\s*['\"`]([^'\"`]+)['\"`]\s*\)\s*\)"
)


def express_router_vars(text: str) -> set:
    """Variable names bound to ``express()`` / ``express.Router()`` in a file.

    Routes are registered on these (``authRouter.post(...)``, ``r.get(...)``), not only on
    the conventional ``app`` / ``router`` names — so the parser must match the real names.
    """
    return {m.group(1) for m in _EX_ROUTER_DEF.finditer(text)}


def _resolve_js_module(from_rel: str, spec: str, file_set: set) -> Optional[str]:
    """Resolve a relative ``require``/``import`` specifier to a project file path."""
    if not spec.startswith("."):
        return None  # node_modules / bare package — out of scope
    base = posixpath.normpath(posixpath.join(posixpath.dirname(from_rel), spec))
    candidates = [
        base, base + ".js", base + ".ts", base + ".mjs", base + ".cjs",
        base + "/index.js", base + "/index.ts",
    ]
    for cand in candidates:
        if cand in file_set:
            return cand
    return None


def build_express(project_root: Path | str) -> dict:
    """Map each file → the ``ResolvedPrefix`` under which its exported router is mounted.

    Files that are never mounted (the root app file, or an unmounted router) resolve to an
    empty prefix, so plain single-file apps are unchanged.
    """
    root = Path(project_root)
    texts: dict[str, str] = {}
    for path in source_files(root, (".js", ".ts", ".mjs", ".cjs"), None):
        texts[path.relative_to(root).as_posix()] = read_text(path)
    file_set = set(texts)

    info: dict[str, dict] = {}
    for rel, text in texts.items():
        routers = {
            m.group(1): ("router" if "Router" in m.group(2) else "app")
            for m in _EX_ROUTER_DEF.finditer(text)
        }
        imports: dict[str, str] = {}
        for m in _EX_REQUIRE.finditer(text):
            tgt = _resolve_js_module(rel, m.group(2), file_set)
            if tgt:
                imports[m.group(1)] = tgt
        for m in _EX_IMPORT.finditer(text):
            tgt = _resolve_js_module(rel, m.group(2), file_set)
            if tgt:
                imports[m.group(1)] = tgt
        mounts = [
            (m.group(1), _norm(m.group(2)), m.group(3)) for m in _EX_MOUNT.finditer(text)
        ]
        require_mounts = []
        for m in _EX_MOUNT_REQUIRE.finditer(text):
            child_file = _resolve_js_module(rel, m.group(3), file_set)
            if child_file:
                require_mounts.append((m.group(1), _norm(m.group(2)), child_file))
        info[rel] = {
            "routers": routers, "imports": imports,
            "mounts": mounts, "require_mounts": require_mounts,
        }

    # child_file -> list of (parent_context, prefix); parent_context "ROOT" or a file rel.
    edges: dict[str, list] = {}
    for rel, d in info.items():
        for parent, prefix, child in d["mounts"]:
            child_file = d["imports"].get(child)
            if child_file is None and child in d["routers"]:
                child_file = rel  # router mounted within its own file
            if child_file is None:
                continue
            parent_context = "ROOT" if d["routers"].get(parent) == "app" else rel
            edges.setdefault(child_file, []).append((parent_context, prefix))
        for parent, prefix, child_file in d["require_mounts"]:
            parent_context = "ROOT" if d["routers"].get(parent) == "app" else rel
            edges.setdefault(child_file, []).append((parent_context, prefix))

    memo: dict[str, ResolvedPrefix] = {}

    def resolve(rel: str, stack: frozenset) -> ResolvedPrefix:
        if rel in memo:
            return memo[rel]
        es = edges.get(rel)
        if not es:
            res = ResolvedPrefix("", True)  # root app file or unmounted → no prefix
        else:
            parent_context, prefix = es[0]
            if parent_context == "ROOT":
                res = ResolvedPrefix(_norm(prefix), True)
            elif parent_context in stack:
                res = ResolvedPrefix(_norm(prefix), False)
            else:
                pres = resolve(parent_context, stack | {rel})
                res = ResolvedPrefix(_join(pres.prefix, prefix), pres.resolved)
        memo[rel] = res
        return res

    return {rel: resolve(rel, frozenset()) for rel in texts}
