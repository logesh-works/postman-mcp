"""Input resolver — OpenAPI first, code parsing fallback, per-route mixing.

Both paths emit the same normalized ``RouteModel``, so everything downstream
is source-agnostic. Resolution is per route: the spec covers what it covers, code
parsing fills the rest, and each route carries its ``source`` label for the diff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ProjectConfig
from postman_mcp.input import openapi as openapi_mod
from postman_mcp.input.detect import detect_openapi_source
from postman_mcp.models import RouteModel, normalize_path


class ResolutionResult:
    """Resolved routes plus notes about any fallback that happened."""

    def __init__(
        self,
        routes: list[RouteModel],
        notes: Optional[list[str]] = None,
        skipped: Optional[list[str]] = None,
    ) -> None:
        self.routes = routes
        self.notes = notes or []
        self.skipped = skipped or []


def _load_openapi_routes(
    config: ProjectConfig, project_root: Path | str
) -> tuple[list[RouteModel], list[str]]:
    """Try the configured spec, then re-detect; return routes + notes."""
    notes: list[str] = []
    source = config.openApiSource or detect_openapi_source(
        project_root, config.framework
    )
    if not source:
        return [], notes
    try:
        spec = openapi_mod.load_spec(source)
        routes = openapi_mod.routes_from_spec(spec)
        return routes, notes
    except openapi_mod.OpenApiError as exc:
        # Spec unreachable / stale → fall back to code for affected routes.
        notes.append(f"OpenAPI source unavailable ({exc}); falling back to code parsing.")
        return [], notes


def resolve_routes(
    config: ProjectConfig,
    project_root: Path | str = ".",
    *,
    only_files: Optional[list[str]] = None,
) -> ResolutionResult:
    """Resolve every route from the best available source, with per-route mixing.

    Strategy:
    1. If inputMode is openapi (or a spec is discoverable), load the spec.
    2. Parse code for the framework.
    3. Merge: spec routes win; code routes fill any METHOD+path the spec missed.

    ``only_files`` narrows the *code* scan to a fixed set of files (incremental syncs),
    so the parser doesn't walk the whole project just to discard most of it afterward.
    """
    notes: list[str] = []
    skipped: list[str] = []

    openapi_routes: list[RouteModel] = []
    if config.inputMode == "openapi" or config.openApiSource:
        openapi_routes, oa_notes = _load_openapi_routes(config, project_root)
        notes.extend(oa_notes)

    # Code parsing fallback (wired per framework in Step E). Returns [] until then.
    code_routes, code_skipped = _parse_code(config, project_root, only_files=only_files)
    skipped.extend(code_skipped)

    merged, collision_notes = _merge_per_route(openapi_routes, code_routes)
    notes.extend(collision_notes)
    if not merged and not openapi_routes and not code_routes:
        notes.append(
            "No routes found from OpenAPI or code. Check config.openApiSource / framework."
        )
    return ResolutionResult(merged, notes, skipped)


def _merge_per_route(
    openapi_routes: list[RouteModel], code_routes: list[RouteModel]
) -> tuple[list[RouteModel], list[str]]:
    """Spec routes take precedence; code fills gaps the spec missed.

    When two *code*-sourced routes collide on the same METHOD+path (e.g. two route
    files both registering ``GET /profile``), silently letting the second overwrite
    the first hides a real ambiguity in the project. Keep the first one parsed and
    surface a note instead, so the user can verify or retarget rather than getting an
    unexplained, possibly-wrong route.
    """
    notes: list[str] = []
    by_key: dict[str, RouteModel] = {}
    for route in code_routes:  # first-seen code route wins; spec may still override below
        existing = by_key.get(route.key)
        if existing is not None:
            notes.append(
                f"⚠ both {existing.code_ref or '?'} and {route.code_ref or '?'} "
                f"register {route.method} {route.path} — using {existing.code_ref or '?'}; "
                "verify with status or retarget explicitly."
            )
            continue
        by_key[route.key] = route
    for route in openapi_routes:
        by_key[route.key] = route
    return list(by_key.values()), notes


def _parse_code(
    config: ProjectConfig,
    project_root: Path | str,
    *,
    only_files: Optional[list[str]] = None,
) -> tuple[list[RouteModel], list[str]]:
    """Dispatch to the framework parser. Wired in Step E."""
    try:
        from postman_mcp.input.parsers import parse_framework

        return parse_framework(config.framework, project_root, only_files=only_files)
    except ModuleNotFoundError:  # a framework parser module not present
        return [], []


# --- target matching for syncapi / sync ----------------------------


def match_target(routes: list[RouteModel], target: str) -> list[RouteModel]:
    """Find routes matching a syncapi target.

    Accepts a ``"METHOD /route"`` string, a function/operationId name, or a path
    fragment. Returns all matches; the caller asks the user when ambiguous.
    """
    target = target.strip()
    matches: list[RouteModel] = []

    # "METHOD /route" form
    parts = target.split(None, 1)
    if len(parts) == 2 and parts[0].upper() in {
        "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"
    }:
        method, path = parts[0].upper(), parts[1].strip()
        wanted = normalize_path(path)
        for r in routes:
            if r.method.upper() == method and normalize_path(r.path) == wanted:
                matches.append(r)
        return matches

    # function name / operationId
    lowered = target.lower()
    for r in routes:
        ref = (r.code_ref or "").lower()
        if ref == lowered or lowered in ref:
            matches.append(r)
    if matches:
        return matches

    # path fragment
    for r in routes:
        if lowered in r.path.lower():
            matches.append(r)
    return matches
