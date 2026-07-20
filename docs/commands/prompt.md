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

1. **Claude picks the scope.** From the instruction it chooses what to analyze — one
   route, a file/module/dir, recent changes, or the whole codebase — and the target. If
   the scope is ambiguous it asks you before doing anything.
2. **Claude folds the "how" directly into what it authors.** Concrete asks — extra error
   responses, headers, an edited description, example values, a persona — go straight
   into the `collection.json`/`metadata.json` Claude writes, cited the same way as any
   other content. Anything added that isn't backed by a citation (an extra example
   response, say) is written without one and shows as unverified in the diff, honestly.
3. **Validate, verify, diff, confirm, write.** Claude calls `sync_files` with `confirm`
   off first; the MCP server validates the collection, re-verifies every citation, and
   returns the diff preview. You're asked **"Write to Postman? [y/n]"**; only on `y` does
   it write.

## What stays deterministic

The MCP tools have **no `prompt` parameter** and run no model. Your instruction is read
by **Claude**, which writes it directly into the collection — there's no separate patch
object the server merges. What the server does is fixed regardless of the instruction:
validate the collection is well-formed, re-read and re-hash every citation, ground every
claimed field against the real code, and diff the result. Route identity, citations, and
field grounding come from your code and stay unaffected by what the instruction says.
Whatever content the instruction adds shows up in the diff before any write, so the
confirm gate fully covers prompt-driven content. See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
