---
description: Sync every API in one file / module / directory. Diff first, write on confirm.
argument-hint: -<file|module|dir> [--into path] [--confirm]
---

Sync every API in one file, module, or directory (PRD §10.1).

Target: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `sync` tool** with `target` set to the
   file/module/dir (strip the leading `-`), plus `into` / `confirm_collection` as given.
   **Leave `confirm` false** (diff only).
2. If the target is ambiguous, the tool returns candidate matches — present them and ask
   the user to choose; never guess (PRD §10.1, §18). Re-call with the chosen target.
3. Show the diff preview verbatim.
4. Ask **"Write to Postman? [y/n]"**; only on yes call again with `confirm: true`.
