# Diff engine

Every write is preceded by a diff in Claude Code. Matching, ordering, and the underlying
change classification (new / modified / unchanged) come from one shared engine
(`postman/merge.py`) no matter which path produced the request; only the rendering
differs by path.

## What the seven slash commands show

`service/filesync.py` renders a plain-text preview, one line per endpoint:

```text
Collection: Acme Backend
Plan: 1 new · 1 modified

[NEW] POST /payments   → payments   ✓ verified (app/payments.py:12)
[MODIFY] PUT /orders/{id}   → orders   ~ stale citation (code moved since cited)

Write to Postman? Re-run with confirm=true to apply.
```

Each line is labelled with what the citation-verification pass found:

- **`✓ verified (file:line)`**: the cited code was re-read and matches exactly what
  Claude claimed.
- **`~ stale citation`**: the citation is well-formed but the code has moved since it was
  cited — usually safe to re-sync.
- **`⚠ CITATION DOES NOT MATCH CODE`**: the cited lines don't back the claim. Excluded
  from the write unless approved explicitly.
- **`· unverified (no citation)`**: content with no citation at all (for example, an
  extra error response added from a `/postman:prompt` instruction) — shown honestly as
  unverified rather than silently trusted.

A preserved test script or saved example shows up as a `preserves:` note under its line;
an excluded endpoint is tagged `[EXCLUDED — <reason>]`.

## What the lower-level tool surface shows

MCP clients calling `syncapi`/`sync`/`syncall`/`syncchanges` directly instead of through a
slash command get a markdown table instead, rendered by `diff/render.py`:

```text
| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | PaymentRequest | PaymentResponse | [code] |
| [MODIFIED] | PUT | /orders/{id} | orders | Bearer | OrderUpdate | OrderResponse | [code] |

Summary: 1 new · 1 modified · 0 deprecated

Write? [y / n]
```

`Target` is the folder the request lands in; it shows `Root Collection` when no `--into`
was given.

### Source labels

`Source` tags where the request's model came from: **`[openapi]`** (a typed spec — high
confidence) or **`[code]`** (parsed from source — confidence varies, and a body inferred
from usage with no schema is flagged lower-confidence in a footnote). See
[per-route mixing](resolver.md#per-route-mixing).

## The two-phase contract

The diff is produced by calling the MCP tool without `confirm`. That call returns the
preview and writes nothing. Only after you answer yes does Claude Code call the tool
again with `confirm: true` to actually perform the write. There's no flag that skips the
diff; you can't write without generating one first. Answer `n` and nothing is written.
Once the result is shown, the command ends. Claude doesn't keep going with more analysis
or commentary after that.
