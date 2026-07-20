"""The ``postman-mcp`` terminal command.

Subcommands:
- ``init``    — the bootstrapper: 6 ordered steps, idempotent.
- ``doctor``  — re-validate the 6-point setup contract.
- ``serve``   — boot the stdio MCP server.
- ``version`` — print the version.

``init``/``doctor`` are *terminal* commands run before Claude Code is wired up; they are
not slash commands. They orchestrate the setup but contain no sync
business logic — that lives in the service layer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer

from postman_mcp import __version__
from postman_mcp.config.store import (
    CONFIG_FILENAME,
    ConfigError,
    PostmanMcpConfig,
    ProjectConfig,
    config_path,
    load_config,
    save_config,
)
from postman_mcp.input.detect import (
    FRAMEWORKS,
    detect_committed_spec,
    detect_project,
    live_spec_candidates,
    verify_live_spec,
)
from postman_mcp.postman.client import PostmanAuthError, PostmanClient, PostmanError
from postman_mcp.secrets.manager import resolve_api_key, store_api_key
from postman_mcp.setup.installer import (
    COMMAND_NAMES,
    install_slash_commands,
    slash_commands_present,
)
from postman_mcp.setup.registration import (
    ensure_gitignore,
    is_server_registered,
    register_mcp_server,
)

app = typer.Typer(
    name="postman-mcp",
    help="Sync API code into Postman collections from Claude Code.",
    add_completion=False,
    no_args_is_help=True,
)

# Reference schemes offered at init.
_KEY_REF_CHOICES = {
    "1": "keychain:postman-mcp",
    "2": "env:POSTMAN_API_KEY",
    "3": "file:postman/secret",
}


def _echo_ok(msg: str) -> None:
    typer.secho(f"✓ {msg}", fg=typer.colors.GREEN)


def _echo_fail(msg: str) -> None:
    typer.secho(f"✗ {msg}", fg=typer.colors.RED)


def _read_api_key() -> str:
    """Read the Postman API key.

    On a real terminal, prompts hidden (as before). ``hide_input=True`` prompts are
    backed by ``getpass``, which on Windows reads directly from the console device —
    it blocks forever if stdin is piped/redirected (CI, automation, `init < answers`)
    since there's no console to read from. Detecting that case up front and reading
    ``POSTMAN_API_KEY`` from the environment instead (or failing fast with a clear
    message if it isn't set) means `init` can never hang waiting for input that can't
    arrive.
    """
    if sys.stdin.isatty():
        return typer.prompt(
            "Postman API key (Postman → Account Settings → API Keys)", hide_input=True
        ).strip()
    env_key = os.environ.get("POSTMAN_API_KEY", "").strip()
    if env_key:
        typer.echo(
            "Non-interactive session detected — using POSTMAN_API_KEY from the environment."
        )
        return env_key
    _echo_fail(
        "Interactive input is unavailable (stdin is not a terminal) and POSTMAN_API_KEY "
        "is not set. Set POSTMAN_API_KEY in your environment, or run `postman-mcp init` "
        "from an interactive terminal."
    )
    raise typer.Exit(code=1)


# --- init ---------------------------------------------------------------------------


@app.command()
def init(
    project_root: Path = typer.Option(
        Path("."), "--path", help="Project root (defaults to CWD)."
    ),
) -> None:
    """Set up this project: key, workspace+collection, config, registration."""
    root = project_root
    existing: Optional[PostmanMcpConfig] = None
    if config_path(root).exists():
        existing = load_config(root)
        typer.echo(f"Existing {CONFIG_FILENAME} found — re-running init (idempotent).")

    # 1. Detect project + input source.
    detected = detect_project(root)
    framework = detected.framework or "unknown"
    if detected.framework:
        framework = typer.prompt(
            f"Detected framework [{detected.framework}] — confirm or override "
            f"({'/'.join(FRAMEWORKS)})",
            default=detected.framework,
        )
    else:
        framework = typer.prompt(
            f"Could not detect framework. Enter one ({'/'.join(FRAMEWORKS)})",
            default="fastapi",
        )
    # OpenAPI-first: prefer a committed spec, then probe the framework's common live
    # spec endpoints (Express/FastAPI/NestJS/Django) so a running spec server is used
    # instead of falling back to code parsing. The probe is best-effort and fast-failing.
    openapi_source = detect_committed_spec(root)
    if not openapi_source:
        probed = verify_live_spec(live_spec_candidates(framework))
        if probed:
            openapi_source = probed
            _echo_ok(f"Found live OpenAPI spec at {probed}")
    openapi_source = openapi_source or detected.openapi_source
    openapi_source = typer.prompt(
        "OpenAPI spec path/URL (blank = parse code)",
        default=openapi_source or "",
    ).strip() or None
    input_mode = "openapi" if openapi_source else "code"
    _echo_ok(f"Framework: {framework} · input mode: {input_mode}")

    # 2. API key handshake. Hidden prompt on a terminal; POSTMAN_API_KEY otherwise.
    api_key = _read_api_key()

    # 3. Store the key by reference.
    if existing:
        default_choice = next(
            (k for k, v in _KEY_REF_CHOICES.items() if v == existing.config.apiKeyRef),
            "1",
        )
    else:
        default_choice = "1"
    typer.echo(
        "Where should the key live?\n"
        "  1) OS keychain (default)\n  2) env:POSTMAN_API_KEY\n"
        "  3) gitignored file postman/secret"
    )
    choice = typer.prompt("Choose", default=default_choice)
    api_key_ref = _KEY_REF_CHOICES.get(choice, _KEY_REF_CHOICES["1"])
    store_api_key(api_key_ref, api_key, root)
    ensure_gitignore(root)

    # Validate the key: GET /me. On 401, stop.
    try:
        with PostmanClient(api_key) as client:
            me = client.validate_key()
            user = me.get("user", {})
            _echo_ok(
                f"Key valid — {user.get('username') or user.get('email') or 'authenticated'}"
            )

            # 4. Pick workspace + collection.
            workspace_id = _pick_workspace(client, existing)
            collection_id = _pick_collection(client, workspace_id, existing, root)
    except PostmanAuthError as exc:
        _echo_fail(str(exc))
        raise typer.Exit(code=1)
    except PostmanError as exc:  # pragma: no cover - network
        _echo_fail(f"Postman API error: {exc}")
        raise typer.Exit(code=1)

    # 5. Write postman-mcp.json.
    cfg = existing or PostmanMcpConfig()
    cfg.config = ProjectConfig(
        framework=framework,
        inputMode=input_mode,
        openApiSource=openapi_source,
        workspace=workspace_id,
        collectionId=collection_id,
        defaultInto=cfg.config.defaultInto if existing else "/",
        apiKeyRef=api_key_ref,
        # V3.0.0 migration (docs/architecture/v3-proposal.md): new projects default to
        # the V3 engine; re-running init on an existing project preserves whatever
        # engine it already had, so upgrading the CLI never silently switches it.
        engine=cfg.config.engine if existing else "v3",
    )
    save_config(cfg, root)
    _echo_ok(f"Config written to {config_path(root)}")

    # 6. Register with Claude Code + install slash commands.
    register_mcp_server(root)
    _echo_ok("MCP server registered with Claude Code")
    install_slash_commands(root)
    _echo_ok(f"{len(COMMAND_NAMES)} slash commands installed")

    typer.echo(
        "\nNext: open Claude Code in this project and run\n"
        "   /postman:syncall          (first full sync)\n"
        "   /postman:syncapi <fn>     (sync one route)"
    )


def _index_of(items: list, key: str, value: Optional[str]) -> Optional[int]:
    """1-based index of the item whose ``key`` matches ``value``, or ``None``."""
    if not value:
        return None
    for i, item in enumerate(items, 1):
        if item.get(key) == value:
            return i
    return None


def _pick_workspace(client: PostmanClient, existing) -> Optional[str]:
    workspaces = client.list_workspaces()
    if not workspaces:
        return None
    typer.echo("\nWorkspaces:")
    for i, ws in enumerate(workspaces, 1):
        typer.echo(f"  {i}) {ws.get('name')}  ({ws.get('id')})")
    # On a re-run, default to whatever workspace is already configured — bare Enter must
    # keep the existing setup instead of silently switching to index 1.
    existing_idx = _index_of(workspaces, "id", existing.config.workspace if existing else None)
    idx = typer.prompt("Pick a workspace", default=str(existing_idx or 1))
    try:
        return workspaces[int(idx) - 1].get("id")
    except (ValueError, IndexError):
        return workspaces[0].get("id")


def _pick_collection(client, workspace_id, existing, root) -> str:
    collections = client.list_collections(workspace_id)
    typer.echo("\nCollections:")
    for i, col in enumerate(collections, 1):
        typer.echo(f"  {i}) {col.get('name')}  ({col.get('uid')})")
    typer.echo(f"  n) create a new collection")
    # On a re-run, default to whatever collection is already configured — bare Enter
    # must keep the existing setup, never silently switch to index 1 or create a
    # duplicate. Only default to "1"/"n" when there's no existing choice to honor.
    existing_idx = _index_of(collections, "uid", existing.config.collectionId if existing else None)
    if existing_idx:
        default_choice = str(existing_idx)
    elif collections:
        default_choice = "1"
    else:
        default_choice = "n"
    choice = typer.prompt(
        "Pick the project's collection (or 'n' for new)", default=default_choice
    )
    if choice.strip().lower() == "n":
        name = typer.prompt("New collection name", default="API Collection")
        created = client.create_collection(
            {"info": {"name": name, "schema": _V21_SCHEMA}, "item": []},
            workspace_id,
        )
        uid = created.get("uid") or created.get("id")
        _echo_ok(f'Created collection "{name}"')
        return uid
    try:
        return collections[int(choice) - 1].get("uid")
    except (ValueError, IndexError):
        return collections[0].get("uid")


_V21_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


# --- doctor -------------------------------------------------------------------------


@app.command()
def doctor(
    project_root: Path = typer.Option(Path("."), "--path", help="Project root."),
) -> None:
    """Re-validate the 6-point setup contract and name what's broken."""
    root = project_root
    ok = True

    # 1. CLI on PATH (we are running, so this passes).
    _echo_ok("postman-mcp CLI is on PATH")

    # 2. postman/config.json exists with a collectionId.
    try:
        cfg = load_config(root)
    except ConfigError as exc:
        _echo_fail(f"{exc}  → fix: postman-mcp init")
        raise typer.Exit(code=1)
    if cfg.config.collectionId:
        _echo_ok(f"{CONFIG_FILENAME} present (collection {cfg.config.collectionId})")
    else:
        _echo_fail(f"{CONFIG_FILENAME} has no collectionId  → fix: postman-mcp init")
        ok = False

    # 3. Key resolves + GET /me returns 200.
    try:
        key = resolve_api_key(cfg.config.apiKeyRef, root)
        with PostmanClient(key) as client:
            client.validate_key()
        _echo_ok("API key resolves and GET /me → 200")
    except (PostmanError, Exception) as exc:
        _echo_fail(f"API key check failed: {exc}  → fix: postman-mcp init")
        ok = False
        client = None  # type: ignore

    # 4. MCP server registered.
    if is_server_registered(root):
        _echo_ok("MCP server registered in .mcp.json")
    else:
        _echo_fail("MCP server not registered  → fix: postman-mcp init")
        ok = False

    # 5. Slash-command md files present.
    if slash_commands_present(root):
        _echo_ok(f"{len(COMMAND_NAMES)} slash commands present under .claude/commands/postman/")
    else:
        _echo_fail("Slash commands missing  → fix: postman-mcp init")
        ok = False

    # 6. Target collection exists (GET /collections/{uid} → 200).
    if cfg.config.collectionId:
        try:
            key = resolve_api_key(cfg.config.apiKeyRef, root)
            with PostmanClient(key) as client:
                col = client.get_collection(cfg.config.collectionId)
            if col:
                _echo_ok("Target collection exists in Postman")
            else:
                _echo_fail("Target collection not found  → fix: postman-mcp init")
                ok = False
        except Exception as exc:
            _echo_fail(f"Collection check failed: {exc}")
            ok = False

    if not ok:
        raise typer.Exit(code=1)
    typer.secho("\nAll setup-contract checks passed.", fg=typer.colors.GREEN)


# --- serve --------------------------------------------------------------------------


@app.command()
def serve() -> None:
    """Boot the stdio MCP server (launched by Claude Code)."""
    from postman_mcp.server import run

    run()


# --- version ------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


def _force_utf8() -> None:
    """Ensure ✓/✗/→ in output don't crash a legacy Windows code page (cp1252)."""
    import sys

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:  # pragma: no cover - best effort
                pass


def main() -> None:  # pragma: no cover - entry point
    _force_utf8()
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
