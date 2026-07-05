# Healthcare prompt

For clinical, patient-data, and other healthcare APIs that need compliance-aware framing.

## Prompt

```text
Act as a healthcare integration architect. Use clinical terminology and HIPAA-aware
framing. Favor realistic but fully synthetic patient examples (never real PHI), and
highlight consent, auth, and audit expectations when you present the diff.
```

## Run it

```text
/postman:prompt "Sync what changed as a healthcare integration architect. Use clinical terminology and HIPAA-aware framing with synthetic patient data only."
```

## What this changes

**Claude** uses the persona to shape its reasoning and how it frames the sync: clinical
terminology, synthetic-data emphasis, and the compliance notes it surfaces alongside the
diff.

## What this does *not* change

The **MCP server stays deterministic.** Route matching, identity, auth detection, request
and response schemas, response contracts, and merge behavior are all computed from your
code — the prompt never touches them. The engine runs no LLM and builds the same Postman
item with or without this prompt.
