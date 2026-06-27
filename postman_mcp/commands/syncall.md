---
description: Sync the WHOLE codebase into the Postman collection. Diff first, write on confirm.
argument-hint: [--into path] [--confirm]
---

Sync every route/controller/model in the codebase. For first-time setup or
post-refactor.

Args: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `syncall` tool** with `into` /
   `confirm_collection` if given. **Leave `confirm` false** — this returns the full diff
   and writes nothing.
2. Show the diff preview verbatim. Each request is labelled `[openapi]` or `[code]` so
   lower-confidence routes are visible.
3. Ask **"Write to Postman? [y/n]"**; only on yes call again with `confirm: true`.
