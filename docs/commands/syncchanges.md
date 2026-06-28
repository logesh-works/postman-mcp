# `/postman:syncchanges`: sync what changed

This is the one you'll run most. After you write code and commit, it syncs only what
changed, and you never have to think about git refs to use it.

## Usage

```text
/postman:syncchanges [--last N] [--since commit|date] [--prompt "…"]
```

## Default behavior

With no flags, it syncs everything changed since `lastUpdate.commit`, the marker written
by your last sync. You never name a git ref yourself.

| Flag | Effect |
|---|---|
| *(none)* | Everything changed since the last sync. |
| `--last 3` | The last 3 commits. No need to remember `HEAD~3` syntax. |
| `--since 2026-06-01` | Everything since a date. |
| `--since a1b2c3d` | Everything since a specific commit. |
| `--prompt "<text>"` | Extra guidance for Claude while it prepares the sync. Consumed by Claude, not the MCP server — see [`--prompt`](#-prompt) below. |

!!! warning "First run with no marker"
    If there's no `lastUpdate.commit` yet, the command errors gently and suggests
    [`/postman:syncall`](syncall.md) for the initial full sync.

## How each change is handled

| Change type | Behavior |
|---|---|
| **New** route | Full create. |
| **Modified** route | Only the changed structural fields are updated; human-owned scripts and examples are preserved. |
| **Deleted** route | Marked deprecated (soft delete). Use `--purge` elsewhere for a hard delete. |

## Why it's cheap

`syncchanges` parses only the files that changed since the last marker, not the whole
project, and reads just the collection's basic structure rather than mirroring it
locally. That's what keeps token usage low enough to run after every change instead of
saving it up.

## Example

```text
<edit routes/payments.py, commit>
/postman:syncchanges

| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [MODIFIED] | POST | /payments | Root Collection | Bearer | PaymentRequest | PaymentResponse | [code] |
| [NEW] | GET | /payments/{id} | Root Collection | Bearer | N/A | PaymentResponse | [code] |

Write? [y / n]
```

Once the write result is shown, the command ends; no further analysis or follow-on
commentary.

## `--prompt`

**Purpose:** provide additional guidance to Claude during synchronization — a persona to
adopt, terminology to use, the example or documentation style to favor.

```text
/postman:syncchanges --prompt "Generate enterprise-grade documentation"
```

**Consumed by:** Claude Code. Claude reads the prompt while preparing the sync and uses it
to shape its reasoning and how it frames the result.

**Not consumed by:** the resolver, the builder, the merge engine, or the Postman client.
The MCP tool has no `prompt` parameter; the engine builds the same deterministic Postman
items whether or not a prompt was given. Prompts influence Claude, never engine structure.
See the [Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
