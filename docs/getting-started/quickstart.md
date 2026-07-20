# Quickstart

This gets you from `pip install` to a populated Postman collection. No manual config
editing required.

## 1. Install

```bash
pip install postman-mcp
```

## 2. Set up this project (once)

Run `init` from your project root. It's idempotent, so it's safe to re-run.

```bash
cd my-api-project
postman-mcp init
```

`init` walks you through six steps, in order:

1. **Detect the project and input source.** It identifies your framework (FastAPI,
   Express, Django, NestJS, Flask, or Spring) and looks for an OpenAPI spec. If it finds
   one, it uses the [OpenAPI path](../architecture/resolver.md); otherwise it parses
   your code.
2. **API-key handshake.** Paste your Postman personal API key. It's validated with
   `GET /me`. **The key is read in the terminal, never typed into a web form and never
   sent to Claude.**
3. **Store the key by reference.** The raw key goes into your OS credential store (the
   default); only a pointer (`apiKeyRef`) is written to config. See
   [Configuration](configuration.md) for the env-var and file fallbacks.
4. **Pick workspace + collection.** Choose the project's collection, or create a new one.
5. **Write `postman/config.json`** at the project root: small, committable, and secret-free.
6. **Register with Claude Code + install slash commands.** This makes the `/postman:*`
   commands appear.

On success you'll see:

```text
✓ Connected to Postman workspace "Acme API" → collection "Acme Backend"
✓ Config written to ./postman/config.json
✓ MCP server registered with Claude Code
✓ 7 slash commands installed

Next: open Claude Code in this project and run
   /postman:syncall          (first full sync)
   /postman:syncapi <fn>     (sync one route)
```

## 3. Use it inside Claude Code

Open Claude Code in the project. Every write-capable command shows a **diff first** and
writes only on confirm.

### Typical first run

Run `/postman:syncall`. You'll see a diff of every route the parser found, then a
`Write? [y / n]` prompt. Say yes and the collection is populated.

### Typical daily run

After you write code and commit, run `/postman:syncchanges`. It diffs only the routes
that changed since your last sync, asks for confirmation, and writes.

### Natural-language sync with `/postman:prompt`

The plain commands take a target, not prose:

```text
/postman:syncapi createPayment
```

For anything free-form — a persona, terminology, a documentation style, or concrete
additions like extra error responses or headers — use
[`/postman:prompt`](../commands/prompt.md). Claude reads the instruction, picks the right
tool and target, and applies the changes through the same diff-then-confirm gate:

```text
/postman:prompt "Sync createPayment using fintech terminology"
```

```text
/postman:prompt "Sync what changed and add the standard error responses"
```

The instruction is read by Claude, not by the MCP server: Claude folds it directly into
the collection it authors, and the MCP server validates and verifies the result the same
way regardless of what prompted it. See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer) and
[`examples/prompts/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/prompts)
for ready-made personas.

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
- Understand the [`postman/config.json` config](configuration.md).
- See how it works under the hood in the [Architecture overview](../architecture/overview.md).
