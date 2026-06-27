"""``createenv`` — generate a Postman environment from code (PRD §10.1, §16).

Variables are inferred from the resolved routes (always from code/spec). Secret-like
names (``key``/``token``/``secret``/``password``) are masked (Postman "secret" type) and
flagged for manual fill. Always adds ``{{base_url}}`` and ``{{token}}`` — the variables
the synced requests reference (PRD §10.1, §16).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from postman_mcp.config.store import ConfigError
from postman_mcp.input.resolver import resolve_routes
from postman_mcp.postman.client import PostmanAuthError, PostmanError
from postman_mcp.secrets.manager import mask_if_secret
from postman_mcp.service.context import load_context


def _infer_variables(routes) -> list[dict[str, Any]]:
    """Collect candidate env variables from headers/query params (PRD §10.1)."""
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
    """Preview (confirm=False) or create (confirm=True) the environment (PRD §13, §16)."""
    try:
        ctx = load_context(project_root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    result = resolve_routes(ctx.config.config, ctx.project_root)
    env_name = name or f"{ctx.config.config.framework or 'api'} env"
    variables = _infer_variables(result.routes)

    if not confirm:
        ctx.client.close()
        lines = [f"ENV PREVIEW — \"{env_name}\"", ""]
        for v in variables:
            flag = "  (secret — masked, fill manually)" if v["type"] == "secret" else ""
            lines.append(f"  {v['key']} = {v['value'] or '<blank>'}{flag}")
        lines.append("")
        lines.append("Create this environment in Postman? [y / n]")
        return "\n".join(lines)

    environment = {"name": env_name, "values": variables}
    try:
        created = ctx.client.create_environment(
            environment, ctx.config.config.workspace
        )
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        return f"Create aborted: {exc}"
    ctx.client.close()
    uid = created.get("uid") or created.get("id") or "?"
    return f'✓ Created environment "{env_name}" ({uid}) with {len(variables)} variables.'
