---
description: Sync ONE API into the Postman collection (the kernel). Diff first, write on confirm.
argument-hint: <function | "METHOD /route" | code> [--into path] [--confirm]
---

Sync a single API into the configured Postman collection (PRD §10.1, §12).

Target: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `syncapi` tool** with `target` set to the
   user's argument, plus `into` / `confirm_collection` if `--into` / `--confirm` were
   given. **Leave `confirm` unset (false) on this first call** — this returns the diff
   preview only and writes nothing (PRD §13, §17).
2. Show the returned diff preview to the user verbatim.
3. Ask: **"Write to Postman? [y/n]"**.
4. Only if the user answers yes, call `syncapi` again with the **same arguments plus
   `confirm: true`** to perform the write.
5. On `n`, stop — nothing is written.

Never call the tool with `confirm: true` before showing the diff and getting a yes.
