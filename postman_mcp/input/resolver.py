"""Input resolver — OpenAPI first, code parsing fallback, per-route mixing (PRD §9).

Both paths emit the same normalized ``RouteModel`` (PRD §9.1), so everything downstream
is source-agnostic. Resolution is per route (§9.5): the spec covers what it covers, code
parsing fills the rest, and each route carries its ``source`` label for the diff (§13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ProjectConfig
from postman_mcp.input import openapi as openapi_mod
from postman_mcp.input.detect import detect_openapi_source
from postman_mcp.models import RouteModel, normalize_path


class ResolutionResult:
    """Resolved routes plus notes about any fallback that happened (PRD §9.5, §18)."""

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
    """Try the configured spec, then re-detect; return routes + notes (PRD §9.2)."""
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
        # Spec unreachable / stale → fall back to code for affected routes (PRD §18).
        notes.append(f"OpenAPI source unavailable ({exc}); falling back to code parsing.")
        return [], notes


def resolve_routes(
    config: ProjectConfig, project_root: Path | str = "."
) -> ResolutionResult:
    """Resolve every route from the best available source, with per-route mixing.

    Strategy (PRD §9.2, §9.5):
    1. If inputMode is openapi (or a spec is discoverable), load the spec.
    2. Parse code for the framework.
    3. Merge: spec routes win; code routes fill any METHOD+path the spec missed.
    """
    notes: list[str] = []
    skipped: list[str] = []

    openapi_routes: list[RouteModel] = []
    if config.inputMode == "openapi" or config.openApiSource:
        openapi_routes, oa_notes = _load_openapi_routes(config, project_root)
        notes.extend(oa_notes)

    # Code parsing fallback (wired per framework in Step E). Returns [] until then.
    code_routes, code_skipped = _parse_code(config, project_root)
    skipped.extend(code_skipped)

    merged = _merge_per_route(openapi_routes, code_routes)
    if not merged and not openapi_routes and not code_routes:
        notes.append(
            "No routes found from OpenAPI or code. Check config.openApiSource / framework."
        )
    return ResolutionResult(merged, notes, skipped)


def _merge_per_route(
    openapi_routes: list[RouteModel], code_routes: list[RouteModel]
) -> list[RouteModel]:
    """Spec routes take precedence; code fills gaps the spec missed (PRD §9.5)."""
    by_key: dict[str, RouteModel] = {}
    for route in code_routes:  # code first so spec overwrites on conflict
        by_key[route.key] = route
    for route in openapi_routes:
        by_key[route.key] = route
    return list(by_key.values())


def _parse_code(
    config: ProjectConfig, project_root: Path | str
) -> tuple[list[RouteModel], list[str]]:
    """Dispatch to the framework parser (PRD §9.4). Wired in Step E."""
    try:
        from postman_mcp.input.parsers import parse_framework

        return parse_framework(config.framework, project_root)
    except ModuleNotFoundError:  # a framework parser module not present
        return [], []


# --- target matching for syncapi / sync (PRD §10.1, §12) ----------------------------


def match_target(routes: list[RouteModel], target: str) -> list[RouteModel]:
    """Find routes matching a syncapi target (PRD §10.1, §12).

    Accepts a ``"METHOD /route"`` string, a function/operationId name, or a path
    fragment. Returns all matches; the caller asks the user when ambiguous (PRD §18).
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
