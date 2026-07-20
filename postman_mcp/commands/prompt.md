---
description: Sync to Postman from a free-form instruction — you read the code and the instruction, the MCP verifies and writes.
argument-hint: "<what to sync and how, in plain English>"
---

The natural-language front-end to the LLM-driven sync. You (the LLM) read both the code and
the instruction, author the collection accordingly, and the MCP validates, verifies your
citations, diffs, and writes on confirm. Works for any framework — there is no parser.

Instruction: `$ARGUMENTS`

## Step 1 — decide the scope from the instruction
Read the instruction and choose what to analyze:

| Instruction implies… | Scope |
|---|---|
| one specific route/function ("the login endpoint", "POST /payments", a pasted handler) | that one endpoint |
| one file, module, or directory ("the users routes", "routes/payments.py") | that scope |
| everything that changed recently ("what I changed", "since last sync") | git-changed endpoints |
| the whole codebase ("everything", "all APIs", first-time setup) | the whole repo |

If the scope is ambiguous, ask the user before doing anything. Only place requests in a
named sub-folder within a module if the user explicitly asks; otherwise use each module's
natural structure.

## Step 2 — author the artifacts, honoring the "how"
1. Call the **`get_sync_contract` tool** once, **with** `skills: ["project-analysis",
   "api-discovery", "auth-discovery", "dto-discovery", "request-builder",
   "response-builder", "folder-builder", "collection-builder", "metadata-builder"]`.
   Read the returned `workflow` doc, then follow the loaded skills. Use
   `index()`/`context()` for discovery and the `cite` tool for citations, per the workflow.
2. Analyze the chosen scope and write to `postman/sync/<module>/collection.json` +
   `metadata.json` for each module touched (the ungrouped `postman/sync/collection.json` +
   `metadata.json` for anything with no real module) — **read a module's existing files
   first, if any, and update/insert only the endpoints in scope**, leaving everything else
   already in that module untouched. Write `postman/sync/sync.config.json` (shared,
   root-level) once. Fold the instruction's *how* directly into what you author — extra
   error responses, extra/edited headers, a rewritten description, adjusted example
   values, a persona for examples, and so on. Cite every endpoint per `metadata-builder`'s
   rules; content you add that isn't in code (e.g. an extra 400 example) simply carries no
   citation and will show as unverified in the diff, which is correct and honest.

## Step 3 — diff, confirm, write (never skip the gate)
3. Call the **`sync_files` tool** with **`confirm: false`** — it returns the verified diff.
4. Show the diff verbatim, then ask **"Write to Postman? [y/n]"**.
5. Only on yes, call `sync_files` again with the same args plus `confirm: true`. On `n`,
   nothing is written. Never call with `confirm: true` before showing the diff and getting a yes.
6. After showing the tool's result, stop. Do not re-run the tool or add commentary. End the turn.
