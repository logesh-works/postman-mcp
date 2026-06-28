---
description: Sync every API in one file / module / directory. Diff first, write on confirm.
argument-hint: -<file|module|dir> [--into path] [--prompt "text"] [--confirm]
---

Sync every API in one file, module, or directory.

Target: `$ARGUMENTS`

If `--prompt "<instructions>"` is present, parse it out first and treat it as
**additional generation guidance for you while preparing this sync** (persona, example
style, validation emphasis, conventions). The `--prompt` text is consumed by you, not by
the MCP server: the `sync` tool is deterministic and has **no `prompt` parameter**, so
never forward `--prompt` to it. Strip it from `target` before calling the tool.

Do this:
1. Call the **`postman-mcp` MCP server's `sync` tool** with `target` set to the
   file/module/dir (strip the leading `-`, and remove any `--prompt "..."`), plus
   `into` / `confirm_collection` as given. **If `--into` was not given, omit `into`
   entirely**: do not infer a folder from the file/module name. Routes go to the
   collection root by default. **Leave `confirm` false** (diff only).
2. If the target is ambiguous, the tool returns candidate matches. Present them and ask
   the user to choose; never guess. Re-call with the chosen target.
3. Show the diff preview verbatim.
4. Ask **"Write to Postman? [y/n]"**; only on yes call again with the same arguments plus
   `confirm: true`.
5. After showing the tool's result, stop. Do not continue analysis, re-run the tool, or
   add commentary. End the turn.
