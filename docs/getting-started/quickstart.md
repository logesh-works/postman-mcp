# Quickstart

From `pip install` to a populated Postman collection in under five minutes — with no
manual config editing.

## 1. Install

```bash
pip install postman-mcp
```

## 2. Set up this project (once)

Run `init` from your project root. It is **idempotent** — safe to re-run.

```bash
cd my-api-project
postman-mcp init
```

`init` walks you through six steps, in order:

1. **Detect the project + input source.** It identifies your framework (FastAPI /
   Express / Django / NestJS) and looks for an OpenAPI spec. If it finds one, it uses the
   [OpenAPI path](../architecture/resolver.md); otherwise it parses your code.
2. **API-key handshake.** Paste your Postman personal API key. It's validated with
   `GET /me`. **The key is read in the terminal — never typed into a web form, never sent
   to Claude.**
3. **Store the key by reference.** The raw key goes into your OS credential store (the
   default); only a pointer (`apiKeyRef`) is written to config. See
   [Configuration](configuration.md) for the env-var and file fallbacks.
4. **Pick workspace + collection.** Choose the project's collection, or create a new one.
5. **Write `postman-mcp.json`** at the project root — small, committable, secret-free.
6. **Register with Claude Code + install slash commands.** This makes the `/postman:*`
   commands appear.

On success you'll see:

```text
✓ Connected to Postman workspace "Acme API" → collection "Acme Backend"
✓ Config written to ./postman-mcp.json
✓ MCP server registered with Claude Code
✓ 6 slash commands installed

Next: open Claude Code in this project and run
   /postman:syncall          (first full sync)
   /postman:syncapi <fn>     (sync one route)
```

## 3. Use it inside Claude Code

Open Claude Code in the project. Every write-capable command shows a **diff first** and
writes only on confirm.

### Typical first run

```text
/postman:syncall          → diff of every route → confirm → collection populated
```

### Typical daily run

```text
<write code, commit>
/postman:syncchanges      → diff of only what changed → confirm → done
```

## Verify the whole setup

Any time something looks off:

```bash
postman-mcp doctor
```

`doctor` checks the [six-point setup contract](configuration.md#the-setup-contract): CLI
on PATH, config present with a valid collection id, API key resolves and `GET /me` returns
200, MCP server registered, slash-command files present, and the target collection still
exists. It names anything broken and gives you the one command to fix it.

## Next steps

- Learn each command in the [Commands reference](../commands/index.md).
- Understand the [`postman-mcp.json` config](configuration.md).
- See how it works under the hood in the [Architecture overview](../architecture/overview.md).
