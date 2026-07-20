---
description: Sync the WHOLE codebase into the Postman collection — you read the code, the MCP verifies and writes.
argument-hint: [--into path] [--confirm]
---

Sync every endpoint in the codebase. You (the LLM) discover and author the collection;
the MCP validates it, re-reads your citations to catch hallucinations, diffs against live
Postman, and writes only on confirm. Works for any framework — there is no parser.

Args: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `get_sync_contract` tool** once, **with**
   `skills: ["project-analysis", "api-discovery", "auth-discovery", "dto-discovery",
   "request-builder", "response-builder", "folder-builder", "collection-builder",
   "metadata-builder"]` — it returns the `workflow` doc plus only those skills (a token
   optimization; omit the param only if you need to browse `available_skills`). Read the
   workflow, then follow the loaded skills. Use `index()`/`context()` for discovery and
   the `cite` tool for citations, per the workflow.
2. Analyze the **whole repository**: discover every endpoint, its method + full path
   (following prefix/mount chains), auth, request body (resolve the DTO/model class,
   including nested and inherited fields), headers, and declared responses.
3. Write `postman/sync/<module>/collection.json` + `postman/sync/<module>/metadata.json`
   per module (`auth/`, `users/`, `orders/`, ...) — one module directory per real
   controller/router/domain in the codebase, per `folder-builder`. Endpoints that don't
   belong to any real module go in the ungrouped `postman/sync/collection.json` +
   `postman/sync/metadata.json` instead.
   - Each `collection.json` — a Postman v2.1 collection fragment (`{{base_url}}` for
     hosts) containing just that module's requests; `info.name` is the module's folder
     name in Postman.
   - Each `metadata.json` — for every request in that module, a `key` (`METHOD:/path`),
     the `citations` proving it exists (file + exact line range + `symbol` +
     `snippet_sha256`), and for bodies/responses the DTO `dto` citation + claimed
     `fields`. This is what keeps you honest — cite the real code.
   - `postman/sync/sync.config.json` (shared, one file, not per module) —
     `scope: "all"`, the configured `collection_id`, your model name, and any `notes`
     (e.g. routes you couldn't statically resolve).
4. Call the **`sync_files` tool** with **`confirm: false`**. Pass `into` only if `--into`
   was given; **if `--into` was not given, omit `into` entirely and do not infer a folder**
   from route/module names — folder structure comes from your `collection.json` files (one
   named folder per module directory), and anything in the ungrouped root lands at the
   collection root by default. The tool returns a diff labelling each endpoint verified /
   stale / ⚠unverified with the cited `file:line`.
5. Show that diff verbatim, then ask **"Write to Postman? [y/n]"**.
6. Only on yes, call `sync_files` again with the same args plus `confirm: true`. If any endpoint
   was excluded for a bad citation, fix the citation in that module's `metadata.json` and
   re-sync rather than blindly approving it.
7. After showing the tool's result, stop. Do not re-run or add commentary. End the turn.
