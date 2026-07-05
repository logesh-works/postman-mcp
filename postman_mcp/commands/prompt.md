---
description: Sync to Postman from a free-form instruction. Diff first, write on confirm.
argument-hint: "<what to sync and how, in plain English>"
---

Sync to the configured Postman collection from a natural-language instruction.

Instruction: `$ARGUMENTS`

This is the natural-language front-end to the sync engine. The MCP sync tools are
deterministic and have **no `prompt` parameter** — so **you** read the instruction,
decide *what* to sync and *how*, and express the "how" as a structured `overrides` patch
that the chosen tool merges onto each built item before the diff. There is no restriction
on what the instruction can ask for: extra error responses, extra/edited headers, a
rewritten description, adjusted example values, a persona for example values, and so on.

## Step 1 — pick the target and tool

Read the instruction and choose exactly one MCP tool by the scope it implies:

| Instruction implies… | Tool | `target` |
|---|---|---|
| one specific route/function ("the login endpoint", "POST /payments", a pasted handler) | `syncapi` | that route / function / code |
| one file, module, or directory ("the users routes", "routes/payments.py") | `sync` | the file/module/dir |
| everything that changed recently ("what I changed", "since last sync") | `syncchanges` | — (optionally map "last N" / "since X") |
| the whole codebase ("everything", "all APIs", first-time setup) | `syncall` | — |

If the scope is ambiguous, ask the user which one before calling anything. Do **not**
infer an `into` folder from names; only pass `into` if the user explicitly names a folder.

## Step 2 — translate the "how" into `overrides`

Build an `overrides` argument: a JSON patch shaped like the Postman item (or any subset).
The tool deep-merges it onto each item — dicts merge key-by-key; lists merge by `key`
(headers) or `name` (responses): a matching entry is updated in place, anything else is
appended. Shape:

```json
{
  "request": {
    "description": "...",                              // replaces the description
    "header": [{"key": "X-Foo", "value": "bar"}]       // merged by key
  },
  "response": [
    {
      "name": "400 Bad Request",                       // merged by name
      "status": "Bad Request",
      "code": 400,
      "header": [{"key": "Content-Type", "value": "application/json"}],
      "body": "{\n  \"detail\": \"Bad Request\"\n}",
      "_postman_previewlanguage": "json"
    }
  ]
}
```

Guidance:
- "add error response(s)" → one `response` entry per status code requested. The standard
  set is 400/401/403/404/422/500; pick the ones relevant to the route(s). Look at the
  diff's existing responses first so your `name`/`status`/`code` don't duplicate them.
- A pure persona/wording instruction with no concrete additions may need **no**
  `overrides` at all — just run the sync and frame the result accordingly.
- When the scope is more than one route (`sync` / `syncall` / `syncchanges`) the one
  patch applies to *every* route in the run, so prefer instructions that make sense
  uniformly (e.g. "add the standard error set") over single-route specifics.

## Step 3 — diff, confirm, write (never skip the gate)

1. Call the chosen tool with `target` (if any) + `overrides` (if any), and **`confirm`
   unset (false)** on this first call — it returns the diff preview and writes nothing.
   For `sync`, if the target is ambiguous the tool returns candidates; present them and
   ask the user to choose, then re-call.
2. Show the returned diff preview verbatim.
3. Ask: **"Write to Postman? [y/n]"**.
4. Only if the user answers yes, call the **same tool with the same arguments plus
   `confirm: true`** to perform the write.
5. On `n`, stop. Nothing is written.
6. After showing the tool's result (the write confirmation or the `n` abort), stop. Do
   not continue analysis, re-run the tool, or add commentary. End the turn.

Never call a tool with `confirm: true` before showing the diff and getting a yes.
