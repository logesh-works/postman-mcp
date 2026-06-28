# `/postman:sync`: file, module, or directory

Syncs every route in one file, module, or directory. Broader than a single route,
narrower than the whole codebase.

## Usage

```text
/postman:sync -<filename|module|directory> [--into path] [--prompt "…"]
```

## Targeting

The target after `-` is fuzzy-matched against your project:

- A **file**, like `-routes/payments.py`
- A **module**, like `-app.api.payments`
- A **directory**, like `-routes/`

If the target is ambiguous, the command lists the candidates and asks you to be
specific. It never guesses.

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Folder inside the collection where the requests land. Missing folders are created automatically. If omitted, falls back to `config.defaultInto`, which defaults to the collection root. No folder gets inferred from the file or module name. |
| `--prompt "<text>"` | Extra guidance for Claude while it prepares the sync. Consumed by Claude, not the MCP server — see [`--prompt`](#-prompt) below. |

## Example

```text
/postman:sync -routes/payments.py --into payments

| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | PaymentRequest | PaymentResponse | [code] |
| [NEW] | GET | /payments/{id} | payments | Bearer | N/A | PaymentResponse | [code] |
| [MODIFIED] | DELETE | /payments/{id} | payments | Bearer | N/A | — | [code] |

Write? [y / n]
```

Each request is matched against the live collection by `METHOD + normalized path`, so
re-running this updates routes in place instead of creating duplicates. See
[idempotency](../architecture/merge-engine.md#idempotency). Once the write result is
shown, the command ends; no further analysis or follow-on commentary.

## `--prompt`

**Purpose:** provide additional guidance to Claude during synchronization — a persona to
adopt, terminology to use, the example or documentation style to favor.

```text
/postman:sync -routes/payments.py --prompt "Use fintech terminology"
```

**Consumed by:** Claude Code. Claude reads the prompt while preparing the sync and uses it
to shape its reasoning and how it frames the result.

**Not consumed by:** the resolver, the builder, the merge engine, or the Postman client.
The MCP tool has no `prompt` parameter; the engine builds the same deterministic Postman
items whether or not a prompt was given. Prompts influence Claude, never engine structure.
See the [Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
