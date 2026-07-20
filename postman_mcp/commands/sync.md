---
description: Sync every API in one file / module / directory — you read the code, the MCP verifies and writes.
argument-hint: -<file|module|dir> [--into path] [--confirm]
---

Sync every endpoint in one file, module, or directory. You (the LLM) discover and author
them; the MCP validates, re-reads your citations to catch hallucinations, diffs against
live Postman, and writes only on confirm. Works for any framework — there is no parser.

Target: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `get_sync_contract` tool** once, **with**
   `skills: ["project-analysis", "api-discovery", "auth-discovery", "dto-discovery",
   "request-builder", "response-builder", "folder-builder", "collection-builder",
   "metadata-builder"]` — it returns the `workflow` doc plus only those skills (a token
   optimization; omit the param only if you need to browse `available_skills`). Read the
   workflow, then follow the loaded skills. Use `index()`/`context()` for discovery and
   the `cite` tool for citations, per the workflow.
2. Analyze **only the file/module/directory** named (strip the leading `-`): every endpoint
   in that scope, its full path (prefix/mount chain), auth, request body (the DTO/model
   class, nested + inherited fields), headers, and declared responses.
3. This scope usually **is** a module — write to `postman/sync/<module>/` where
   `<module>` is the target name (reuse an already-existing module directory if one
   clearly corresponds to this target; don't create a near-duplicate with a slightly
   different name). If the scope spans several unrelated modules (a directory containing
   more than one), split across each module's own directory instead of inventing one
   combined module. Endpoints that don't belong to any real module go in the ungrouped
   `postman/sync/` root.
   - `collection.json` — **if it already exists from an earlier sync, read it first** and
     update/insert just this scope's requests, leaving every other request already in the
     file untouched (`{{base_url}}` host).
   - `metadata.json` next to it — same merge rule: update/insert just these endpoints'
     `key`, `citations`, and body/response DTO `dto` citation + claimed `fields`; leave
     other endpoints' entries untouched.
   - `postman/sync/sync.config.json` (shared, root-level) with `scope: "file"`, `target`,
     the configured `collection_id`.
4. Call the **`sync_files` tool** with **`confirm: false`**. Pass `into` only if `--into`
   was given; **if `--into` was not given, omit `into` entirely and do not infer a folder**
   from the file/module name — placement comes from which module directory (or the root)
   you wrote to, and requests in the ungrouped root go to the collection root by default.
5. Show the returned diff verbatim (each endpoint labelled verified / stale / ⚠unverified
   with its cited `file:line`), then ask **"Write to Postman? [y/n]"**.
6. Only on yes, call `sync_files` again with the same args plus `confirm: true`. If an
   endpoint was excluded for a bad citation, fix that module's `metadata.json` and re-sync
   rather than blindly approving.
7. After showing the tool's result, stop. Do not re-run the tool or add commentary. End the turn.
