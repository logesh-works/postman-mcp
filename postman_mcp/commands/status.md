---
description: Read-only drift check — what WOULD sync, without writing anything.
argument-hint: [--since commit|date|last]
---

Show what would sync — new / modified / deprecated routes and anything drifted from
code — **without writing**. This is `syncall`'s diff minus the write.

Args: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `status` tool**, mapping `--since X` → `since`.
2. Show the report verbatim. This command never writes to Postman — there is no confirm
   step.
