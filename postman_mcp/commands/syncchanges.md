---
description: Sync what changed since the last sync (the daily driver). Diff first, write on confirm.
argument-hint: [--last N] [--since commit|date]
---

Sync everything that changed since the last sync (PRD §10.1).

Args: `$ARGUMENTS`

Do this:
1. Call the **`postman-mcp` MCP server's `syncchanges` tool**. With no flags it syncs
   everything changed since `lastUpdate.commit`. Map `--last N` → `last`, `--since X`
   → `since`. **Leave `confirm` false** on this first call (diff only; PRD §13).
2. If the tool reports there is no last-sync marker, tell the user to run
   `/postman:syncall` first (PRD §18) and stop.
3. Show the diff preview verbatim. New routes create fully; modified routes change only
   structural fields (human-owned scripts/examples preserved); deleted routes are
   soft-deprecated (PRD §10.1, §15).
4. Ask **"Write to Postman? [y/n]"**; only on yes call again with `confirm: true`.
