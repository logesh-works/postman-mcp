# `/postman:syncchanges` — sync what changed

The **daily driver**. After you write code and commit, this syncs only what changed —
with zero thought about git refs.

## Usage

```text
/postman:syncchanges [--last N] [--since commit|date]
```

## Default behavior

With **no flags**, it syncs everything changed since `lastUpdate.commit` (the marker
written by your last sync). You never name a git ref.

| Flag | Effect |
|---|---|
| *(none)* | Everything changed since the last sync. |
| `--last 3` | The last 3 commits (no `HEAD~3` syntax to remember). |
| `--since 2026-06-01` | Everything since a date. |
| `--since a1b2c3d` | Everything since a specific commit. |

!!! warning "First run with no marker"
    If there's no `lastUpdate.commit` yet, the command errors gently and suggests
    [`/postman:syncall`](syncall.md) for the initial full sync.

## How each change is handled

| Change type | Behavior |
|---|---|
| **New** route | Full create. |
| **Modified** route | Only the changed structural fields are updated; human-owned scripts and examples are preserved. |
| **Deleted** route | Marked deprecated (soft delete). Use `--purge` elsewhere for hard delete. |

## Why it's cheap

`syncchanges` parses **only the files changed** since the last marker and reads just the
collection's basic structure — never a full re-scan. That keeps token usage low, which is
the whole point of running it after every change.

## Example

```text
<edit routes/payments.py, commit>
/postman:syncchanges

SYNC PREVIEW — 2 changes since a1b2c3d
~ POST /payments      body: + idempotency_key (string)        [modified] [openapi]
+ GET  /payments/{id}                                          [new]      [openapi]

Write? [y / n]
```
