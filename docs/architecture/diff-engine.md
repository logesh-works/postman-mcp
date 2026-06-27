# Diff engine

Every write is preceded by a diff in Claude Code. The diff engine renders the before/after
so nothing reaches Postman by surprise — and so you can see, at a glance, which requests
came from a typed spec versus heuristic code parsing.

Module: `diff/render.py`.

## A new request

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

## A modified request

Modified requests show **field-level `~` changes** and explicitly list what is
**preserved** (human-owned scripts and examples):

```text
SYNC PREVIEW — PUT /orders/{id}  →  collection / orders   [MODIFIED] [code]

~ Body       + include_items (boolean)
~ Responses  + 409 Conflict
= Preserved  2 test scripts, 1 manual example (human-owned)

Write? [y / n]
```

## Source labels

Each request is tagged with where its model came from:

- **`[openapi]`** — derived from a typed OpenAPI spec. High confidence.
- **`[code]`** — derived from code parsing. Lower confidence, especially for untyped
  bodies (e.g. Express). Worth a closer look.

This makes [per-route mixing](resolver.md#per-route-mixing-prd-95) visible: in one diff
you might see most routes `[openapi]` and a manually mounted one `[code]`.

## The two-phase contract

The diff is produced by calling the MCP tool **without** `confirm` — it returns the
preview and writes nothing. Only after you answer **yes** does Claude Code call the tool
again with `confirm: true` to perform the write. There is **no skip flag**: you cannot
write without first generating a diff. On `n`, nothing is written.
