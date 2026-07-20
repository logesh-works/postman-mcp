---
description: Generate a Postman environment from code (secrets masked) — you read the code, the MCP creates it.
argument-hint: [env_name]
---

Create a Postman environment whose variables you (the LLM) infer from the code's config,
base URLs, and secret usage. The MCP validates and creates it; it never reads source.

Name: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `get_sync_contract` tool** once, **with**
   `skills: ["project-analysis", "environment-discovery"]` — this command needs only 2 of
   the 10 skills (no DTO/request/response guidance), so requesting just those keeps the
   contract payload small. Read the `workflow` doc, then follow the two loaded skills.
2. Analyze the project per `environment-discovery`: base URL(s), auth tokens, API keys,
   and any config-driven values the requests reference.
3. Write `postman/sync/environment.json` (`{name, values:[{key,value,type,enabled}]}`),
   naming it from the argument or a sensible default.
4. Call the **`sync_env` tool** with **`confirm: false`** — it returns a preview of the
   variables (secrets flagged, masked).
5. Show the preview, then ask **"Create this environment in Postman? [y/n]"**; only on yes
   call `sync_env` again with `confirm: true`.
6. After showing the tool's result, stop. Do not re-run the tool or add commentary. End the turn.
