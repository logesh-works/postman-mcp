---
description: Sync the WHOLE codebase into the Postman collection. Diff first, write on confirm.
argument-hint: [--into path] [--prompt "text"] [--confirm]
---

Sync every route/controller/model in the codebase. For first-time setup or
post-refactor.

Args: `$ARGUMENTS`

If `--prompt "<instructions>"` is present, parse it out first and treat it as
**additional generation guidance for you while preparing this sync** (persona, example
style, validation emphasis, conventions). The `--prompt` text is consumed by you, not by
the MCP server: the `syncall` tool is deterministic and has **no `prompt` parameter**, so
never forward `--prompt` to it.

Do this:
1. Call the **`postman-mcp` MCP server's `syncall` tool** with `into` /
   `confirm_collection` if given. **If `--into` was not given, omit `into` entirely**:
   do not infer a folder per route or module. Routes go to the collection root by
   default. **Leave `confirm` false**, since this returns the full diff and writes
   nothing.
2. Show the diff preview verbatim. Each request is labelled `[openapi]` or `[code]` so
   lower-confidence routes are visible.
3. Ask **"Write to Postman? [y/n]"**; only on yes call again with the same arguments plus
   `confirm: true`.
4. After showing the tool's result, stop. Do not continue analysis, re-run the tool, or
   add commentary. End the turn.
