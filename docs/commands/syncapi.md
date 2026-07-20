# `/postman:syncapi`: sync one API

The most surgical of the five commands. It syncs exactly one route and touches nothing
else. Every other command is just a different way of picking which routes go through the
same validate → verify → diff → confirm → write pipeline this one uses directly.

## Usage

```text
/postman:syncapi <function_name | "METHOD /route" | "pasted code"> [--into path] [--confirm]
```

For free-form instructions (add error responses, headers, an edited description, a
persona, …), use [`/postman:prompt`](prompt.md) instead.

## Targeting

You can identify the route three ways:

- **Function name**, like `create_payment`
- **Route string**, like `"POST /payments/refund"`
- **Pasted code**, a snippet of the handler

If the target is ambiguous (the same name matches more than one route), the command
lists the candidates and asks you to be specific. It never guesses.

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Folder inside the collection where the request lands, for example `payments` or `auth/oauth`. Missing folders are created automatically. If omitted, falls back to `config.defaultInto`, which defaults to the collection root. No folder gets inferred from the route or function name. |
| `--confirm` | Only required when targeting a collection other than the configured default. A safety rail, not something you'll normally need. |

## Example

```text
/postman:syncapi create_payment --into payments
```

```text
Collection: Acme Backend
Plan: 1 new · 0 modified

[NEW] POST /payments   → payments   ✓ verified (app/payments.py:12)

Write to Postman? Re-run with confirm=true to apply.
```

Each line is labelled `✓ verified` (the citation matches your code), `~ stale` (the code
moved since it was cited), or `⚠ CITATION DOES NOT MATCH CODE` — so you can see which
requests are backed by real code before you say yes. An endpoint that fails verification
is excluded from the write unless you name it explicitly.

## What happens, step by step

1. **Find the endpoint.** Claude uses the repository index to locate `create_payment`
   and read the exact code it needs — the handler, its request/response types, and its
   route registration — without reading the project unbounded.
2. **Author the request.** Claude writes a complete Postman request (method, path,
   params, body, auth, responses) into `collection.json`, plus a `file:line` citation for
   every claimed fact in `metadata.json`.
3. **Validate and verify.** The MCP server checks the collection is well-formed,
   re-reads every cited line to confirm it matches what Claude claimed, and grounds every
   claimed request/response field against the real DTO/model class.
4. **Diff.** The server reads the live collection, matches `POST /payments` by
   `METHOD + normalized path`, and renders the before/after preview — a new request if no
   match is found, resolving `--into payments` to a folder (creating it if needed).
5. **Confirm.** The diff is always shown. A non-default collection target additionally
   needs `--confirm`.
6. **Write.** Merge into the collection JSON and `PUT /collections/{uid}`.
7. **Record.** Update `lastUpdate` in `postman/config.json`. Claude shows the write result
   and stops; no further analysis or follow-on commentary.

Updating an existing route follows the same steps. Step 4 finds the existing request
instead of creating one, and step 7 merges into it in place. Its test scripts and manual
examples are read back from Postman and preserved; only the structural fields change.
See the [merge engine](../architecture/merge-engine.md).

## Free-form instructions

`syncapi` itself is plain and deterministic — it takes a target, not prose. For anything
free-form (add error responses, extra headers, an edited description, example values, a
persona), use [`/postman:prompt "<text>"`](prompt.md). Claude reads the instruction,
targets this same single-route sync under the hood, and applies the changes through the
same diff-then-confirm gate. See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
