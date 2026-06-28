# Fintech prompt

For payments, ledgers, transfers, and other money-movement APIs.

## Prompt

```text
Act as a Stripe API architect. Use fintech terminology, money-as-minor-units
conventions, and enterprise-grade validation framing. Favor realistic payment examples
(amounts, currencies, idempotency keys) and call out auth and error-handling expectations
when you present the diff.
```

## Run it

```text
/postman:syncapi createPayment --prompt "Act as a Stripe API architect. Use fintech terminology and enterprise-grade validation framing."
```

## What this changes

**Claude** uses the persona to shape its reasoning and how it frames the sync: the
terminology in its summary, the kind of examples and validations it suggests, the
follow-up edits it offers.

## What this does *not* change

The **MCP server stays deterministic.** Route matching, identity, auth detection, request
and response schemas, response contracts, and merge behavior are all computed from your
code — the prompt never touches them. The engine runs no LLM and builds the same Postman
item with or without this prompt.
