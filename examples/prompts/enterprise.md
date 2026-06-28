# Enterprise prompt

For internal platform APIs that need formal, consistent documentation.

## Prompt

```text
Use enterprise API documentation style. Write formal, complete descriptions; use
consistent naming and a professional tone; and note versioning, auth, and rate-limit
expectations when you present the diff.
```

## Run it

```text
/postman:syncall --prompt "Use enterprise API documentation style with formal descriptions and consistent naming."
```

## What this changes

**Claude** uses the guidance to shape its reasoning and how it frames the sync: a formal
documentation tone, consistent naming in its summary, and the platform concerns it calls
out. One prompt applies to the whole `syncall` run, so keep it broad.

## What this does *not* change

The **MCP server stays deterministic.** Route matching, identity, auth detection, request
and response schemas, response contracts, and merge behavior are all computed from your
code — the prompt never touches them. The engine runs no LLM and builds the same Postman
items with or without this prompt.
