# `/postman:prompt`: natural-language sync

The natural-language front-end to the sync engine. Describe what you want in plain
English and Claude figures out *what* to sync and *how*, then runs it through the same
diff-then-confirm gate as every other command. This replaces the old `--prompt` flag that
used to hang off the individual sync commands.

## Usage

```text
/postman:prompt "<what to sync and how, in plain English>"
```

Examples:

```text
/postman:prompt "add error responses to the payments routes"
/postman:prompt "give every endpoint an X-Request-Id header"
/postman:prompt "sync the login endpoint and rewrite its description as a Stripe-style architect"
/postman:prompt "add the standard 4xx/5xx error set to the whole codebase"
```

## How it works

1. **Claude picks the scope and tool.** From the instruction it chooses one underlying
   tool — `syncapi` (one route), `sync` (a file/module/dir), `syncchanges` (recent
   changes), or `syncall` (whole codebase) — and the target. If the scope is ambiguous it
   asks you before doing anything.
2. **Claude translates the "how" into an `overrides` patch.** Concrete asks — extra error
   responses, headers, an edited description, example values, a persona — become a
   structured JSON patch shaped like the Postman item. The engine deep-merges it onto each
   built item: dicts merge key-by-key; lists merge by `key` (headers) / `name`
   (responses), updating matches in place and appending the rest.
3. **Diff, confirm, write.** The chosen tool runs with `confirm` off first and returns the
   diff preview; you're asked **"Write to Postman? [y/n]"**; only on `y` does it write.

## What stays deterministic

The MCP tools have **no `prompt` parameter** and run no model. Your instruction is
consumed by **Claude**, which turns it into a structured `overrides` patch — *data, not
prose* — that the deterministic engine merges before the diff. Route matching, identity,
auth detection, and schema inference come from your code regardless of what the
instruction says; `overrides` only ever adjusts the request/response *content* of items
already matched to their routes. Whatever the patch adds shows up in the diff before any
write, so the confirm gate fully covers prompt-driven content. See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
