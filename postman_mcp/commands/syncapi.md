---
description: Sync ONE API into the Postman collection (the kernel). Diff first, write on confirm.
argument-hint: <function | "METHOD /route" | code> [--into path] [--confirm]
---

Sync a single API into the configured Postman collection.

Target: `$ARGUMENTS`

For free-form instructions (add error responses, extra headers, an edited description,
example values, a persona, ...), use **`/postman:prompt "<text>"`** instead — it
translates natural language into the sync and applies it through the same diff/confirm
gate. This command is the plain, deterministic single-API sync.

Do this:
1. Call the **`postman-mcp` MCP server's `syncapi` tool** with `target` set to the
   user's argument, plus `into` / `confirm_collection` if `--into` / `--confirm` were
   given. **If `--into` was not given, omit `into` entirely**: do not infer a folder or
   module name from the route or function. The route goes to the collection root by
   default. **Leave `confirm` unset (false) on this first call**, since this returns the
   diff preview only and writes nothing.
2. Show the returned diff preview to the user verbatim.
3. Ask: **"Write to Postman? [y/n]"**.
4. Only if the user answers yes, call `syncapi` again with the **same arguments plus
   `confirm: true`** to perform the write.
5. On `n`, stop. Nothing is written.
6. After showing the tool's result (the write confirmation or the `n` abort), stop. Do
   not continue analysis, re-run the tool, or add commentary. End the turn.

Never call the tool with `confirm: true` before showing the diff and getting a yes.
