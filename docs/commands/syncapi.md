# `/postman:syncapi`: sync one API

The most surgical of the five commands. It syncs exactly one route and touches nothing
else. Every other command is just a different way of picking which routes to hand to the
same engine that this one calls directly.

## Usage

```text
/postman:syncapi <function_name | "METHOD /route" | "pasted code"> [--into path] [--prompt "…"] [--confirm]
```

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
| `--prompt "<text>"` | Extra guidance for Claude while it prepares the sync. Consumed by Claude, not the MCP server — see [`--prompt`](#-prompt) below. |
| `--confirm` | Only required when targeting a collection other than the configured default. A safety rail, not something you'll normally need. |

## Example

```text
/postman:syncapi create_payment --into payments
```

```text
| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | PaymentRequest | PaymentResponse | [code] |

Summary: 1 new · 0 modified · 0 deprecated

Write? [y / n]
```

## What happens, step by step

1. **Resolve the target.** The resolver finds `create_payment` and turns it into a
   normalized route model.
2. **Parse.** Extract method, path, body type, auth middleware, response models, and
   docstring.
3. **Build.** The [engine](../architecture/engine.md) assembles the full request object.
4. **Read the collection.** `GET` the collection and scan its structure for an existing
   `POST /payments`. If it's not found, this is a new request. Resolve `--into payments`
   to a folder, creating it if it doesn't exist.
5. **Diff.** Render the preview in Claude Code.
6. **Confirm.** The diff is always shown. A non-default collection target additionally
   needs `--confirm`.
7. **Write.** Merge into the collection JSON and `PUT /collections/{uid}`.
8. **Record.** Update `lastUpdate` in `postman-mcp.json`. Claude shows the write result
   and stops; no further analysis or follow-on commentary.

Updating an existing route follows the same steps. Step 4 finds the existing request
instead of creating one, and step 7 merges into it in place. Its test scripts and manual
examples are read back from Postman and preserved; only the structural fields change.
See the [merge engine](../architecture/merge-engine.md).

## `--prompt`

**Purpose:** provide additional guidance to Claude during synchronization — a persona to
adopt, terminology to use, the example or documentation style to favor.

```text
/postman:syncapi createPayment --prompt "Act as a Stripe API architect"
```

**Consumed by:** Claude Code. Claude reads the prompt while preparing the sync and uses it
to shape its reasoning and how it frames the result.

**Not consumed by:** the resolver, the builder, the merge engine, or the Postman client.
The MCP tool has no `prompt` parameter; the engine builds the same deterministic Postman
item whether or not a prompt was given. Prompts influence Claude, never engine structure
(route matching, identity, auth detection, schemas, response contracts, merge behavior).
See the [Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
