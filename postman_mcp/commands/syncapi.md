---
description: Sync ONE API into the Postman collection (the kernel) — you read the code, the MCP verifies and writes.
argument-hint: <function | "METHOD /route" | code> [--into path] [--confirm]
---

Sync a single endpoint. You (the LLM) find and author it; the MCP validates, re-reads your
citations to catch hallucinations, diffs against live Postman, and writes only on confirm.
Works for any framework — there is no parser.

Target: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `get_sync_contract` tool** once, **with**
   `skills: ["project-analysis", "api-discovery", "auth-discovery", "dto-discovery",
   "request-builder", "response-builder", "folder-builder", "collection-builder",
   "metadata-builder"]` — it returns the `workflow` doc plus only those skills (a token
   optimization; omit the param only if you need to browse `available_skills`). Read the
   workflow, then follow the loaded skills. Use `index()`/`context()` for discovery and
   the `cite` tool for citations, per the workflow.
2. Locate the **single endpoint** named by the target (a function/handler name, a
   `"METHOD /path"`, or a file). Resolve its full path (prefix/mount chain), auth, request
   body (the DTO/model class, nested + inherited fields), headers, and declared responses.
3. Identify which module this endpoint belongs to (per `folder-builder`) — an existing
   `postman/sync/<module>/` if one already fits, a new one if it's the first endpoint for
   that module, or the ungrouped `postman/sync/` root if it truly doesn't belong to any
   module. Write:
   - `collection.json` (in that module's directory, or the root) — **if the file already
     exists from an earlier sync, read it first** and update/insert just this one request,
     leaving every other request already in that file untouched; otherwise create it fresh
     containing just this one request (`{{base_url}}` host).
   - `metadata.json` next to it — same merge rule: update/insert just this endpoint's
     `key`, `citations` (file + exact lines + `symbol` + `snippet_sha256`), and the
     body/response DTO `dto` citation + claimed `fields`; leave other endpoints' entries
     already in the file untouched.
   - `postman/sync/sync.config.json` (shared, root-level) with `scope: "api"`, `target`,
     the configured `collection_id`.
4. Call the **`sync_files` tool** with **`confirm: false`**. Pass `into` only if `--into`
   was given; **if `--into` was not given, omit `into` entirely and do not infer a folder**
   from the route or function name — placement comes from which module directory (or the
   root) you wrote to, and requests in the ungrouped root land at the collection root by
   default.
5. Show the returned diff verbatim (it labels the endpoint verified / stale / ⚠unverified
   with the cited `file:line`), then ask **"Write to Postman? [y/n]"**.
6. Only on yes, call `sync_files` again with the same args plus `confirm: true`. Never call
   with `confirm: true` before showing the diff and getting a yes. On `n`, nothing is written.
7. After showing the tool's result, stop. Do not re-run the tool or add commentary. End the turn.
