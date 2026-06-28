"""Sync orchestration — the five selectors over one engine.

Every write-capable entry follows the two-phase ``confirm`` contract: with
``confirm=False`` it returns the rendered diff and writes nothing; with ``confirm=True``
it re-runs and performs the merge + ``PUT``. All four selectors funnel
through :func:`_run_sync`, which holds the safety rails.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ConfigError, ProjectConfig, save_config
from postman_mcp.diff.render import render_plan
from postman_mcp.engine.builder import build_request_item
from postman_mcp.input.resolver import match_target, resolve_routes
from postman_mcp.models import ChangeType, RouteModel, SyncPlan
from postman_mcp.postman import merge
from postman_mcp.postman.client import PostmanAuthError, PostmanError
from postman_mcp.service.context import SyncContext, load_context


# --- public selectors ---------------------------------------------------------------


def sync_api(
    target: str,
    *,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    project_root: Path | str = ".",
) -> str:
    """Sync ONE API — the kernel."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    result = resolve_routes(ctx.config.config, ctx.project_root)
    matches = match_target(result.routes, target)
    if not matches:
        return (
            f"No route matched {target!r}. "
            "Try a function name, \"METHOD /route\", or a path fragment."
        )
    if len(matches) > 1:
        # Ambiguous — list candidates, never guess.
        listed = "\n".join(f"  - {r.method} {r.path}" for r in matches)
        return (
            f"{target!r} is ambiguous — matched {len(matches)} routes:\n{listed}\n"
            'Re-run with a precise target like "POST /payments".'
        )
    return _run_sync(
        ctx, matches, into=into, confirm=confirm,
        confirm_collection=confirm_collection, notes=result.notes,
    )


def sync_all(
    *,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    project_root: Path | str = ".",
) -> str:
    """Sync the whole codebase."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"
    result = resolve_routes(ctx.config.config, ctx.project_root)
    if not result.routes:
        return "No routes found. " + " ".join(result.notes)
    return _run_sync(
        ctx, result.routes, into=into, confirm=confirm,
        confirm_collection=confirm_collection, notes=result.notes,
        skipped=result.skipped,
    )


def sync_target(
    target: str,
    *,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    project_root: Path | str = ".",
) -> str:
    """Sync every API in one file / module / directory."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"
    result = resolve_routes(ctx.config.config, ctx.project_root)
    routes = _filter_by_file(result.routes, target)
    if not routes:
        return (
            f"No routes found in {target!r}. Check the file/module/dir path."
        )
    return _run_sync(
        ctx, routes, into=into, confirm=confirm,
        confirm_collection=confirm_collection, notes=result.notes,
        skipped=result.skipped,
    )


def sync_changes(
    *,
    last: Optional[int] = None,
    since: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    project_root: Path | str = ".",
) -> str:
    """Sync what changed since the last sync. Daily driver."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    from postman_mcp.git.reader import GitError, changed_files, resolve_since

    anchor = since
    if anchor is None and last is None:
        anchor = ctx.config.lastUpdate.commit
        if not anchor:
            # First run with no marker → error gently, suggest syncall.
            return (
                "No last-sync marker yet. Run /postman:syncall for the first full "
                "sync, then /postman:syncchanges will track changes from there."
            )
    try:
        files = changed_files(
            ctx.project_root, last=last, since=resolve_since(anchor) if anchor else None
        )
    except GitError as exc:
        return f"Error reading git history: {exc}"

    if not files:
        return "No changed files since the last sync — nothing to do."

    # Narrow the code parse to just the changed files instead of scanning the whole
    # project then filtering after — the token/work saving for the daily driver.
    result = resolve_routes(ctx.config.config, ctx.project_root, only_files=files)
    routes = _filter_by_changed_files(result.routes, files)
    if not routes:
        return (
            "Changed files contain no recognizable routes "
            f"({len(files)} file(s) changed)."
        )
    return _run_sync(
        ctx, routes, into=into_default(ctx), confirm=confirm,
        confirm_collection=confirm_collection, notes=result.notes,
        skipped=result.skipped,
    )


def into_default(ctx: SyncContext) -> Optional[str]:
    return ctx.config.config.defaultInto


# --- the shared engine (safety rails live here) -------------------------------------


def _run_sync(
    ctx: SyncContext,
    routes: list[RouteModel],
    *,
    into: Optional[str],
    confirm: bool,
    confirm_collection: bool,
    notes: Optional[list[str]] = None,
    skipped: Optional[list[str]] = None,
) -> str:
    """Build → diff → (confirm gate) → write. The only path that touches Postman."""
    into_path = _resolve_into(into, ctx.config.config)
    gen_tests = ctx.config.config.generateTests  # owner preference: OFF by default
    style = ctx.config.config.responseStyle  # "single" = one best response (default)

    built = [
        (r, build_request_item(r, generate_tests=gen_tests, response_style=style))
        for r in routes
    ]

    plan = SyncPlan(
        collection_id=ctx.collection_id,
        collection_name=ctx.collection_name,
        diffs=[
            merge.compute_diff(ctx.collection, item, route, into_path)
            for route, item in built
        ],
        skipped=skipped or [],
    )

    # --- preview phase: diff only, no write ---
    if not confirm:
        ctx.client.close()
        preview = render_plan(plan)
        if notes:
            preview = "\n".join(notes) + "\n\n" + preview
        return preview

    # --- write phase ---
    if not plan.has_changes:
        ctx.client.close()
        return "Nothing to write — already up to date."

    working = copy.deepcopy(ctx.collection)
    new = mod = 0
    for route, item in built:
        change = merge.apply_route(working, item, route, into_path)
        if change is ChangeType.NEW:
            new += 1
        else:
            mod += 1

    try:
        ctx.client.update_collection(ctx.collection_id, working)
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        return f"Write aborted (no partial write): {exc}"

    # Record lastUpdate, then return a single, explicit completion summary so the
    # operation has an unambiguous end state (Issue 9).
    _record_sync(ctx)
    ctx.client.close()
    return _completion_summary(new, mod, into_path)


def _resolve_into(into: Optional[str], config: ProjectConfig) -> str:
    """Deterministic, user-controlled placement (Issue 10).

    Precedence — nothing else:
      1. Explicit ``--into`` target.
      2. Configured ``config.defaultInto`` (when set to a real folder).
      3. The collection root (``"/"``).

    Never infers a folder from the route/file/module name, and never invents collection
    structure. ``"/"`` means the request lands at the collection root; the merge layer
    only materializes a folder for an explicit/configured non-root target.
    """
    if into is not None and into.strip():
        return into.strip()
    configured = (config.defaultInto or "").strip()
    if configured and configured != "/":
        return configured
    return "/"


def _completion_summary(new: int, mod: int, into_path: str) -> str:
    """The explicit end-state summary returned after a successful write."""
    lines: list[str] = []
    if new:
        lines.append(f"✓ {new} API(s) added")
    if mod:
        lines.append(f"✓ {mod} API(s) updated")
    where = "collection root" if into_path == "/" else f'folder "{into_path}"'
    lines.append(f"✓ Collection updated ({where})")
    lines.append("✓ lastUpdate recorded")
    lines.append("✓ Sync completed")
    return "\n".join(lines)


def _record_sync(ctx: SyncContext) -> None:
    from postman_mcp.git.reader import current_commit

    commit = current_commit(ctx.project_root)
    ctx.config.mark_synced(commit)
    save_config(ctx.config, ctx.project_root)


# --- route filters ------------------------------------------------------------------


def _filter_by_file(routes: list[RouteModel], target: str) -> list[RouteModel]:
    """Filter routes whose code_ref/path matches a file/module/dir."""
    needle = target.strip().lstrip("-").strip().lower()
    out: list[RouteModel] = []
    for r in routes:
        ref = (r.code_ref or "").lower()
        if needle in ref or needle in r.path.lower():
            out.append(r)
    return out


def _filter_by_changed_files(
    routes: list[RouteModel], files: list[str]
) -> list[RouteModel]:
    """Keep routes whose source file is among the changed files."""
    changed = {Path(f).as_posix().lower() for f in files}
    out: list[RouteModel] = []
    for r in routes:
        ref = (r.code_ref or "")
        ref_posix = Path(ref).as_posix().lower() if ref else ""
        if any(ref_posix and ref_posix in c or (c and c in ref_posix) for c in changed):
            out.append(r)
    # If routes have no file refs (pure OpenAPI), fall back to syncing all on change.
    if not out and routes and all(not r.code_ref or "/" not in (r.code_ref or "") for r in routes):
        return routes
    return out
