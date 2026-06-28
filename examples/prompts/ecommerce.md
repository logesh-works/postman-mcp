# Ecommerce prompt

For storefront, cart, catalog, and order APIs.

## Prompt

```text
Act as an ecommerce platform architect. Use Indian ecommerce examples (INR pricing, local
addresses and names) and storefront terminology. Favor realistic cart, catalog, and order
examples, and highlight inventory and payment-status edge cases when you present the diff.
```

## Run it

```text
/postman:syncapi createOrder --prompt "Act as an ecommerce platform architect. Use Indian ecommerce examples and storefront terminology."
```

## What this changes

**Claude** uses the persona to shape its reasoning and how it frames the sync: localized
examples, storefront terminology, and the edge cases it surfaces alongside the diff.

## What this does *not* change

The **MCP server stays deterministic.** Route matching, identity, auth detection, request
and response schemas, response contracts, and merge behavior are all computed from your
code — the prompt never touches them. The engine runs no LLM and builds the same Postman
item with or without this prompt.
