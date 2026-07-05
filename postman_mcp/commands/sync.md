---
description: Sync every API in one file / module / directory. Diff first, write on confirm.
argument-hint: -<file|module|dir> [--into path] [--confirm]
---

Sync every API in one file, module, or directory.

Target: `$ARGUMENTS`

For free-form instructions (add error responses, extra headers, a rewritten description,
example values, ...), use **`/postman:prompt "<text>"`** instead. This command is the
plain, deterministic file/module/dir sync.

Do this:
1. Call the **`postman-mcp` MCP server's `sync` tool** with `target` set to the
   file/module/dir (strip the leading `-`), plus `into` / `confirm_collection` as given.
   **If `--into` was not given, omit `into` entirely**: do not infer a folder
   from the file/module name. Routes go to the collection root by default. **Leave
   `confirm` false** (diff only).
2. If the target is ambiguous, the tool returns candidate matches. Present them and ask
   the user to choose; never guess. Re-call with the chosen target.
3. Show the diff preview verbatim.
4. Ask **"Write to Postman? [y/n]"**; only on yes call again with the same arguments plus
   `confirm: true`.
5. After showing the tool's result, stop. Do not continue analysis, re-run the tool, or
   add commentary. End the turn.
