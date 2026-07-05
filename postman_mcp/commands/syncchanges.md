---
description: Sync what changed since the last sync (the daily driver). Diff first, write on confirm.
argument-hint: [--last N] [--since commit|date]
---

Sync everything that changed since the last sync.

Args: `$ARGUMENTS`

For free-form instructions (add error responses, extra headers, a rewritten description,
...), use **`/postman:prompt "<text>"`** instead. This command is the plain, deterministic
changed-routes sync.

Do this:
1. Call the **`postman-mcp` MCP server's `syncchanges` tool**. With no flags it syncs
   everything changed since `lastUpdate.commit`. Map `--last N` → `last`, `--since X`
   → `since`. **Leave `confirm` false** on this first call (diff only).
2. If the tool reports there is no last-sync marker, tell the user to run
   `/postman:syncall` first and stop.
3. Show the diff preview verbatim. New routes create fully; modified routes change only
   structural fields (human-owned scripts/examples preserved); deleted routes are
   soft-deprecated.
4. Ask **"Write to Postman? [y/n]"**; only on yes call again with the same arguments plus
   `confirm: true`.
5. After showing the tool's result, stop. Do not continue analysis, re-run the tool, or
   add commentary. End the turn.
