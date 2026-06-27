# `/postman:syncapi` — sync one API

The **kernel**. The most surgical command: it syncs exactly one API and touches nothing
else. If pointing at one function and watching a complete request materialize feels like
magic, everything else is just a different selector over the same engine.

## Usage

```text
/postman:syncapi <function_name | "METHOD /route" | "pasted code"> [--into path] [--confirm]
```

## Targeting

You can identify the route three ways:

- **Function name** — `createPayment`
- **Route string** — `"POST /payments/refund"`
- **Pasted code** — a snippet of the handler

If the target is ambiguous, the command lists candidates and asks — it never guesses
silently.

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Folder inside the collection where the request lands (e.g. `payments`, `auth/oauth`). Missing folders are auto-created. Omitted → `config.defaultInto`. |
| `--confirm` | Required only when targeting a collection other than the configured default (a safety rail). |

## Example

```text
/postman:syncapi createPayment --into payments
```

```text
SYNC PREVIEW — POST /payments  →  collection / payments   [NEW] [openapi]

+ Request    POST {{base_url}}/payments
+ Auth       Bearer {{token}}              (from require_auth middleware)
+ Body       { "amount": 4200, "currency": "USD", "method": "card" }
+ Responses  201 Created, 400, 401, 422, 500
+ Tests      status(201) · schema(PaymentResponse) · business(amount > 0)
+ Examples   1 success, 4 error

Write? [y / n]
```

## What happens, step by step

1. **Resolve target** — the resolver finds `createPayment` → a normalized route model.
2. **Parse** — extract method, path, body type, auth middleware, response models, docstring.
3. **Build** — the [engine](../architecture/engine.md) assembles the full request object.
4. **Read collection** — `GET` the collection, scan its structure for an existing
   `POST /payments`. Not found → it's new. Resolve `--into payments` to the folder (create
   if missing).
5. **Diff** — render the preview in Claude Code.
6. **Confirm** — the diff is always shown; a non-default collection target needs `--confirm`.
7. **Write** — merge into the collection JSON, `PUT /collections/{uid}`.
8. **Record** — update `lastUpdate` in `postman-mcp.json`.

Updating an existing API is identical, except step 4 *finds* the request and step 7 merges
in place. Its test scripts and manual examples are read from Postman and **preserved** —
only structural fields change. See the [merge engine](../architecture/merge-engine.md).
