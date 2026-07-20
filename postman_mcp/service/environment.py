"""``createenv`` — generate a Postman environment from code.

Variables are inferred from the resolved routes (always from code/spec). Secret-like
names (``key``/``token``/``secret``/``password``) are masked (Postman "secret" type) and
flagged for manual fill. Always adds ``{{base_url}}`` and ``{{token}}`` — the variables
the synced requests reference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from postman_mcp.config.store import ConfigError, save_config
from postman_mcp.input.resolver import resolve_routes
from postman_mcp.postman.client import PostmanAuthError, PostmanError
from postman_mcp.secrets.manager import mask_if_secret
from postman_mcp.service.context import load_context
from postman_mcp.service.filesync import find_existing_environment


def _infer_variables(routes) -> list[dict[str, Any]]:
    """Collect candidate env variables from headers/query params."""
    names: dict[str, bool] = {}
    # Base variables every synced request references.
    names["base_url"] = False
    names["token"] = True  # token is secret-like → masked
    for route in routes:
        for p in [*route.headers, *route.query_params]:
            if mask_if_secret(p.name):
                names[p.name] = True
    variables: list[dict[str, Any]] = []
    for name, secret in names.items():
        variables.append(
            {
                "key": name,
                "value": "" if secret else _default_value(name),
                "type": "secret" if secret else "default",
                "enabled": True,
            }
        )
    return variables


def _default_value(name: str) -> str:
    if name == "base_url":
        return "http://localhost:8000"
    return ""


def create_env(
    *,
    name: Optional[str] = None,
    confirm: bool = False,
    project_root: Path | str = ".",
) -> str:
    """Preview (confirm=False) or create/update (confirm=True) the environment.

    Looks up an existing managed environment the same way ``sync_env`` does
    (:func:`postman_mcp.service.filesync.find_existing_environment`) and updates it in
    place instead of creating a duplicate on every re-run.
    """
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    result = resolve_routes(ctx.config.config, ctx.project_root)
    env_name = name or f"{ctx.config.config.framework or 'api'} env"
    variables = _infer_variables(result.routes)
    existing_uid, _ = find_existing_environment(
        ctx.client, ctx.config.config.workspace, ctx.config.config.environmentId, env_name,
    )

    if not confirm:
        ctx.client.close()
        lines = [f"ENV PREVIEW: \"{env_name}\"", ""]
        for v in variables:
            flag = "  (secret, masked, fill manually)" if v["type"] == "secret" else ""
            lines.append(f"  {v['key']} = {v['value'] or '<blank>'}{flag}")
        lines.append("")
        verb = "Update" if existing_uid else "Create"
        lines.append(f"{verb} this environment in Postman? [y / n]")
        return "\n".join(lines)

    environment = {"name": env_name, "values": variables}
    try:
        if existing_uid:
            result_env = ctx.client.update_environment(existing_uid, environment)
            uid = existing_uid
        else:
            result_env = ctx.client.create_environment(
                environment, ctx.config.config.workspace
            )
            uid = result_env.get("uid") or result_env.get("id") or "?"
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        return f"{'Update' if existing_uid else 'Create'} aborted: {exc}"

    ctx.config.config.environmentId = uid
    save_config(ctx.config, ctx.project_root)
    ctx.client.close()
    verb = "Updated" if existing_uid else "Created"
    return f'✓ {verb} environment "{env_name}" ({uid}) with {len(variables)} variables.'
