---
description: Generate a Postman environment from code (dummy vars; secrets masked). Diff first.
argument-hint: [env_name]
---

Create a Postman environment with variables inferred from code.

Name: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `createenv` tool** with `name` set to the
   argument (or let it default). **Leave `confirm` false**; this returns a preview of
   the variables that would be created.
2. Show the preview. Secret-like values (`key`/`token`/`secret`/`password`) are masked
   and flagged for manual fill; `{{base_url}}` and `{{token}}` are included.
3. Ask **"Create this environment in Postman? [y/n]"**; only on yes call again with
   `confirm: true`.
4. After showing the tool's result, stop. Do not continue analysis, re-run the tool, or
   add commentary. End the turn.
