---
description: Sync the WHOLE codebase into the Postman collection. Diff first, write on confirm.
argument-hint: [--into path] [--confirm]
---

Sync every route/controller/model in the codebase. For first-time setup or
post-refactor.

Args: `$ARGUMENTS`

For free-form instructions (add error responses, extra headers, a rewritten description,
...), use **`/postman:prompt "<text>"`** instead. This command is the plain, deterministic
whole-codebase sync.

Do this:
1. Call the **`postman-mcp` MCP server's `syncall` tool** with `into` /
   `confirm_collection` if given.
   **If `--into` was not given, omit `into` entirely**: do not infer a folder per route or
   module. Routes go to the collection root by default. **Leave `confirm` false**, since
   this returns the full diff and writes nothing.
2. Show the diff preview verbatim. Each request is labelled `[openapi]` or `[code]` so
   lower-confidence routes are visible.
3. Ask **"Write to Postman? [y/n]"**; only on yes call again with the same arguments plus
   `confirm: true`.
4. After showing the tool's result, stop. Do not continue analysis, re-run the tool, or
   add commentary. End the turn.
