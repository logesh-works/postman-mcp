# Commands

After [`postman-mcp init`](../getting-started/quickstart.md), seven slash commands are
available inside Claude Code. The sync commands aren't separate implementations: they all
build the same complete Postman request through the same engine, and differ only in which
routes they pick and where the result lands.

| Command | One-liner |
|---|---|
| [`/postman:syncapi`](syncapi.md) | Sync one route. The kernel that everything else is built on. |
| [`/postman:syncchanges`](syncchanges.md) | Sync what changed since the last sync. The one you'll run most. |
| [`/postman:sync`](sync.md) | Sync everything in one file, module, or directory. |
| [`/postman:syncall`](syncall.md) | Sync the whole codebase. Usually a first-run or post-refactor thing. |
| [`/postman:prompt`](prompt.md) | Sync from a plain-English instruction (add error responses, headers, etc.). |
| [`/postman:createenv`](createenv.md) | Generate a Postman environment from your code. |
| [`/postman:status`](status.md) | Show drift without writing anything. |

## The diff-then-confirm contract

Every write-capable command follows the same two-phase contract, so nothing reaches
Postman as a surprise:

```mermaid
sequenceDiagram
    participant You
    participant CC as Claude Code
    participant S as MCP server
    participant P as Postman
    You->>CC: /postman:syncapi create_payment
    CC->>S: syncapi(target, confirm=false)
    S->>P: GET collection (read structure)
    S-->>CC: diff preview (writes nothing)
    CC-->>You: diff table ... Write? [y/n]
    You->>CC: y
    CC->>S: syncapi(target, confirm=true)
    S->>P: PUT merged collection
    S-->>CC: written
```

On `n`, nothing is written. There's no flag to skip this step; see the
[safety rules](../architecture/overview.md#safety). Once the result is shown (either the
write confirmation or the `n` abort), the command ends. Claude doesn't keep going with
more analysis or commentary after that.

## Natural-language sync with `/postman:prompt`

For free-form instructions — "add error responses to the payments routes", "give every
endpoint an `X-Request-Id` header", "rewrite the login description" — use
[`/postman:prompt "<text>"`](prompt.md). Claude reads the instruction, picks the right
sync tool and target, and expresses the "how" as a structured `overrides` patch the
engine merges before the diff. The instruction is **consumed by Claude, not by the MCP
server**, which has no `prompt` parameter and stays deterministic; everything still goes
through the same diff-then-confirm gate. See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).

## Terminal vs. Claude Code

The `/postman:*` commands above run inside Claude Code. Setup commands run in the
terminal and aren't slash commands:

- `postman-mcp init`: one-time project setup.
- `postman-mcp doctor`: re-validate the whole setup chain.
- `postman-mcp serve`: boot the MCP server (Claude Code launches this for you, you
  shouldn't need to run it by hand).
- `postman-mcp version`: print the version.
