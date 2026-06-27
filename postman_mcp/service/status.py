"""``status`` — read-only drift check (PRD §10.2). ``syncall``'s diff minus the write.

Shows what *would* sync — new / modified / deprecated routes and anything drifted from
code — without writing anything (no confirm step).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ConfigError
from postman_mcp.diff.render import render_status
from postman_mcp.engine.builder import build_request_item
from postman_mcp.input.resolver import resolve_routes
from postman_mcp.models import ChangeType, InputSource, RequestDiff, SyncPlan
from postman_mcp.postman import merge
from postman_mcp.postman.client import PostmanAuthError, PostmanError
from postman_mcp.service.context import load_context


def status_report(
    *, since: Optional[str] = None, project_root: Path | str = "."
) -> str:
    """Compute drift without writing (PRD §10.2)."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    result = resolve_routes(ctx.config.config, ctx.project_root)
    into = ctx.config.config.defaultInto or "/"
    diffs: list[RequestDiff] = []
    code_keys: set[str] = set()
    for route in result.routes:
        code_keys.add(route.key)
        item = build_request_item(
            route,
            generate_tests=ctx.config.config.generateTests,
            response_style=ctx.config.config.responseStyle,
        )
        diffs.append(merge.compute_diff(ctx.collection, item, route, into))

    # Routes present in Postman but gone from code → would be soft-deprecated (PRD §15).
    for parent, _idx, item in merge._iter_request_items(ctx.collection.get("item", [])):
        key = merge.item_key(item)
        if key and key not in code_keys and not (item.get("name", "")).startswith(
            "[DEPRECATED]"
        ):
            method, _, path = key.partition(":")
            diffs.append(
                RequestDiff(
                    change=ChangeType.DEPRECATED,
                    method=method,
                    path=path,
                    into=into,
                    source=result.routes[0].source if result.routes else InputSource.CODE,
                )
            )

    ctx.client.close()
    plan = SyncPlan(
        collection_id=ctx.collection_id,
        collection_name=ctx.collection_name,
        diffs=diffs,
        skipped=result.skipped,
    )
    report = render_status(plan)
    if result.notes:
        report = "\n".join(result.notes) + "\n\n" + report
    return report
