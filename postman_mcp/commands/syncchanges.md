---
description: Sync what changed since the last sync (the daily driver) — you read the diff, the MCP verifies and writes.
argument-hint: [--last N] [--since commit|date]
---

Sync everything that changed since the last sync. You (the LLM) inspect the git changes,
author the affected endpoints; the MCP validates, verifies your citations, diffs against
live Postman, and writes only on confirm. Works for any framework — there is no parser.

Args: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `get_sync_contract` tool** once, **with**
   `skills: ["project-analysis", "api-discovery", "auth-discovery", "dto-discovery",
   "request-builder", "response-builder", "folder-builder", "collection-builder",
   "metadata-builder"]` — it returns the `workflow` doc plus only those skills (a token
   optimization; omit the param only if you need to browse `available_skills`). Read the
   workflow, then follow the loaded skills. Use `index()`/`context()` for discovery and
   the `cite` tool for citations, per the workflow.
2. Determine what changed: run git for the range implied by the args — no flags means since
   the last sync (`postman/config.json` → `lastUpdate.commit`); `--last N` = last N commits;
   `--since X` = since commit/date X. If there is no last-sync marker and no flags, tell the
   user to run `/postman:syncall` first and stop.
3. Analyze **only the endpoints in the changed files**, per the loaded skills. Note any
   route removed from code in `sync.config.json` notes (deletion handling stays manual for now).
4. For each changed endpoint, identify which module it belongs to and update **only that
   module's** `postman/sync/<module>/collection.json` + `metadata.json` — **read the
   existing files first** and update/insert just the changed endpoint(s), leaving every
   other endpoint already in that module's files untouched. Endpoints not belonging to any
   real module go in the ungrouped `postman/sync/collection.json` + `metadata.json`
   instead, same merge rule. Don't touch modules with no changed endpoints. Write
   `postman/sync/sync.config.json` (scope `"changes"`, shared, root-level) per
   `metadata-builder`'s citation rules.
5. Call the **`sync_files` tool** with **`confirm: false`**; show the returned diff verbatim
   (each endpoint labelled verified / stale / ⚠unverified with its cited `file:line`), then
   ask **"Write to Postman? [y/n]"**.
6. Only on yes, call `sync_files` again with the same args plus `confirm: true`. Modified
   endpoints keep human-owned scripts/examples; fix any excluded endpoint's citation and
   re-sync rather than approving blindly.
7. After showing the tool's result, stop. Do not re-run the tool or add commentary. End the turn.
