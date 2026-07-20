---
description: Read-only drift check — what WOULD sync, without writing anything.
argument-hint: [--since commit|date|last]
---

Show what would sync (new, modified, drifted endpoints) without writing anything. Same
LLM-driven discovery as `syncall`, but preview-only — the write step is never reached.

Args: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `get_sync_contract` tool** once, **with**
   `skills: ["project-analysis", "api-discovery", "auth-discovery", "dto-discovery",
   "request-builder", "response-builder", "folder-builder", "collection-builder",
   "metadata-builder"]` — it returns the `workflow` doc plus only those skills (a token
   optimization; omit the param only if you need to browse `available_skills`). Read the
   workflow, then follow the loaded skills. Use `index()`/`context()` for discovery and
   the `cite` tool for citations, per the workflow.
2. Analyze the repository (or, if `--since X` is given, focus on what changed since X) and
   write `postman/sync/<module>/collection.json` + `metadata.json` per module touched (the
   ungrouped `postman/sync/collection.json` + `metadata.json` for anything with no real
   module), plus `postman/sync/sync.config.json` (scope `"status"`, shared, root-level) —
   per the loaded skills, with citations + DTO field claims. Read a module's existing
   files first, if any, and preserve every endpoint not in scope.
3. Call the **`sync_files` tool** with **`confirm: false`**. This returns the drift preview:
   each endpoint as NEW / MODIFY, labelled verified / stale / ⚠unverified with its cited
   `file:line`, plus any preserved human-owned fields.
4. Show the report verbatim. **This command never writes** — do not call `sync_files` with
   `confirm: true`, and do not ask to write. End the turn.
