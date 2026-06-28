# Diff engine

Every write is preceded by a diff in Claude Code. The diff engine renders it as a
markdown table, so you can scan the whole change set at once: which requests are new vs.
modified, where each one lands, and whether it came from a typed spec or heuristic code
parsing.

Module: `diff/render.py`. Columns: `Status | Method | Route | Target | Auth | Body |
Response | Source`.

## New and modified requests

```text
| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | PaymentRequest | PaymentResponse | [code] |
| [MODIFIED] | PUT | /orders/{id} | orders | Bearer | OrderUpdate | OrderResponse | [code] |

Summary: 1 new · 1 modified · 0 deprecated

Write? [y / n]
```

`Target` is the folder the request lands in. It shows `Root Collection` when no `--into`
was given. Every route in one sync run shares the same target; nothing gets auto-foldered
per route based on its name or path. `Body` and `Response` show the named type the engine
resolved, or `N/A`/`—` when there isn't one. Anything that doesn't fit in a cell, like a
low-confidence warning or a note about preserved fields, shows up as a footnote under the
table:

```text
  ⚠ PUT /orders/{id}: lower confidence (body inferred, not from a type)
  PUT /orders/{id}, Preserved (human-owned): test scripts, saved examples / responses
```

## Source labels

Each request is tagged with where its model came from:

- **`[openapi]`**: derived from a typed OpenAPI spec. High confidence.
- **`[code]`**: derived from code parsing. Confidence varies. A typed body (a Pydantic
  model, a DTO, a validated schema) is just as trustworthy as OpenAPI; a body inferred
  from how `req.body` is used in an Express handler with no schema and no JSDoc is not,
  and gets flagged as lower confidence in the footnotes.

This makes [per-route mixing](resolver.md#per-route-mixing) visible. In one diff you
might see most routes tagged `[openapi]` and a manually mounted one tagged `[code]`.

## The two-phase contract

The diff is produced by calling the MCP tool without `confirm`. That call returns the
preview and writes nothing. Only after you answer yes does Claude Code call the tool
again with `confirm: true` to actually perform the write. There's no flag that skips the
diff; you can't write without generating one first. Answer `n` and nothing is written.
Once the result is shown, the command ends. Claude doesn't keep going with more analysis
or commentary after that.
