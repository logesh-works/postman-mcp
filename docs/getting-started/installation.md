# Installation

## Requirements

- **Python ≥ 3.10**
- **[Claude Code](https://claude.com/claude-code)** installed (the `init` command checks
  for it; if absent, it prints instructions and still writes config so you can register
  manually)
- A **Postman account** with a [personal API key](https://learning.postman.com/docs/developer/postman-api/authentication/)
- `git` on your PATH (used by `syncchanges` to detect what changed)

## Install from PyPI

```bash
pip install postman-mcp
```

This single package delivers four things:

1. The **CLI** — the `postman-mcp` command.
2. The **MCP server** — a local stdio server that Claude Code launches.
3. The **slash-command markdown** files — copied into your project on `init`.
4. The **engine, parsers, and Postman client** that do the real work.

After install, verify it's on your PATH:

```bash
postman-mcp version
```

!!! note "Nothing is connected yet"
    `pip install` only puts the bits on disk. All wiring — the API-key handshake,
    workspace/collection selection, MCP-server registration, and slash-command install —
    happens in [`postman-mcp init`](quickstart.md). Run it once per project.

## Recommended: pipx or uv

To keep the CLI isolated from your project environments:

=== "pipx"

    ```bash
    pipx install postman-mcp
    ```

=== "uv"

    ```bash
    uv tool install postman-mcp
    ```

## Install from source (for contributors)

```bash
git clone https://github.com/logesh-works/postman-mcp
cd postman-mcp
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS / Linux:        source .venv/bin/activate
pip install -e ".[dev]"
```

See the [contributing guide](../development/contributing.md) for the full development
setup.

## Next steps

[Set up your first project with `postman-mcp init` →](quickstart.md){ .md-button .md-button--primary }
