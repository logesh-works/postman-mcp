# Postman MCP for Claude Code — Product Requirements Document

**Status:** MVP scope locked · **Version:** 3.1 (full setup + OpenAPI-first input) · **Owner:** Backend Developer (you) / Product

This version is the build-ready spec. Everything from v2.1 plus the part that was implicit before: **the complete setup chain** — what gets installed, what the user types in the terminal, what `postman-mcp init` actually does, how the server registers itself in Claude Code, and how the slash commands become available. Read §A–§E first; they are the new core. The rest is the locked product spec.

---

# PART I — SETUP (the end-to-end chain)

## A. The whole journey in one view

```
TERMINAL                          TERMINAL                      CLAUDE CODE
┌──────────────────┐   ┌────────────────────────────┐   ┌─────────────────────────┐
│ pip install      │──▶│ postman-mcp init           │──▶│ /postman:syncapi ...    │
│ postman-mcp      │   │  • API key handshake       │   │ /postman:syncchanges    │
│                  │   │  • pick workspace+collection│   │ /postman:syncall        │
│ (gets the CLI +  │   │  • write postman-mcp.json  │   │ /postman:createenv      │
│  MCP server +    │   │  • register MCP server in  │   │ /postman:status         │
│  slash-command   │   │    Claude Code             │   │                         │
│  md files)       │   │  • install slash commands  │   │ (all commands live)     │
└──────────────────┘   └────────────────────────────┘   └─────────────────────────┘
        1                          2                              3
```

Three user actions total: **install**, **init**, then **use inside Claude Code**. Steps 1–2 are terminal; step 3 is all inside Claude Code. After init, the user never touches the terminal again for normal work.

---

## B. Step 1 — `pip install postman-mcp`

A single pip-installable package delivers four things:

1. **The CLI** — the `postman-mcp` command (entry point: `postman-mcp = postman_mcp.cli:main`).
2. **The MCP server** — a local stdio MCP server (`postman_mcp.server`) that Claude Code launches.
3. **The slash-command markdown files** — the `/postman:*` command definitions, bundled in the package and copied into the project on `init`.
4. **The engine + parsers + Postman client** — all the Python that does the real work (§Part II).

### Package layout
```
postman-mcp/
├── pyproject.toml                 # entry points, deps, version
├── postman_mcp/
│   ├── __init__.py
│   ├── cli.py                     # `postman-mcp` command: init, doctor, version
│   ├── server.py                  # MCP server (stdio); one tool per command
│   ├── engine/                    # code → Postman request object (§8)
│   ├── input/                     # input resolver (§9)
│   │   ├── resolver.py            #   OpenAPI-available? decision + per-route mixing
│   │   ├── openapi.py            #   OpenAPI 3.x → route model (preferred path)
│   │   └── parsers/               #   fallback: fastapi.py, express.py, django.py, nestjs.py
│   ├── postman/                   # REST client for api.getpostman.com (§6)
│   ├── git/                       # "what changed since X" (§5)
│   ├── config/                    # read/write postman-mcp.json (§7)
│   ├── secrets/                   # keychain / env / file resolver (§6.2)
│   └── commands/                  # slash-command md templates (shipped, copied on init)
│       ├── syncapi.md
│       ├── syncchanges.md
│       ├── sync.md
│       ├── syncall.md
│       ├── createenv.md
│       └── status.md
└── README.md
```

### Dependencies (MVP)
- `mcp` (the Python MCP SDK) — server transport + tool registration.
- `httpx` — Postman REST calls.
- `pydantic` — internal route-model validation **and** FastAPI body introspection.
- `keyring` — OS credential store access.
- `gitpython` (or shelling to `git`) — diff since commit.
- `typer` or `click` — the CLI.

### Requirements
- Python ≥ 3.10.
- Claude Code installed (the CLI checks for it in `init`; if absent, it prints install instructions and still writes config so the user can register manually).
- A Postman account with a personal API key.

After install, **nothing is connected yet**. `pip install` only puts the bits on disk. All wiring happens in `init`.

---

## C. Step 2 — `postman-mcp init` (the bootstrapper)

This is the command your earlier plan called "postman init." It is a **terminal** command (`postman-mcp init`), run once per project from the project root. It is the only place setup happens. It does six things, in order, and is **idempotent** — safe to re-run.

### C.1 What `init` does, in order

**1. Detect the project + input source.**
Walk the project root, detect the framework (FastAPI / Express / Django / NestJS) by signature files (`main.py` + `fastapi` import, `package.json` + `express`, `manage.py`, `@nestjs/core`). Confirm with the user; let them override. Store as `config.framework`. Then look for an **OpenAPI spec** (§9.2) — explicit path, live `/openapi.json` endpoint, or committed `openapi.{json,yaml}`. If found, set `config.inputMode = "openapi"` and `config.openApiSource`; otherwise `config.inputMode = "code"`. The user can point at a spec URL/path manually here.

**2. API key handshake** (§6.3).
Prompt for the Postman personal API key (link them to Postman → Account Settings → API Keys). Validate with `GET /me`. On 401, stop and explain how to generate a valid key. **The key is read in the terminal by the CLI directly from the user — never typed into a web form, never sent to Claude.**

**3. Store the key by reference** (§6.2).
Write the raw key to the OS credential store (default) via `keyring`. Store only a pointer (`config.apiKeyRef = "keychain:postman-mcp"`) in the json. Fallbacks: `env:POSTMAN_API_KEY`, or a gitignored `.postman-mcp.secret`. The CLI asks which the user prefers; keychain is the default.

**4. Pick workspace + collection.**
`GET /workspaces` → user picks one. `GET /collections` → user picks the **project's collection**, or chooses "create a new one" (`POST /collections`). Save `workspace` and `collectionId`.

**5. Write `postman-mcp.json`** (§7) at project root. Small, committable, secret-free.

**6. Register with Claude Code + install slash commands** (§C.2). This is the step that makes the `/postman:*` commands appear.

On success, print exactly what the user does next:
```
✓ Connected to Postman workspace "Acme API" → collection "Acme Backend"
✓ Config written to ./postman-mcp.json
✓ MCP server registered with Claude Code
✓ 6 slash commands installed

Next: open Claude Code in this project and run
   /postman:syncall          (first full sync)
   /postman:syncapi <fn>     (sync one route)
```

### C.2 How registration actually works

Two mechanisms, both handled by `init` so the user doesn't hand-edit anything:

**(a) Register the MCP server.** `init` adds the server to Claude Code's MCP config (project-scoped `.mcp.json`, or via `claude mcp add` if the CLI is present). The entry launches the stdio server:
```json
{
  "mcpServers": {
    "postman-mcp": {
      "command": "postman-mcp",
      "args": ["serve"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```
`postman-mcp serve` boots `postman_mcp.server`, which exposes one MCP tool per command (§10). The server reads `postman-mcp.json` from `cwd` on startup to know the target collection.

**(b) Install the slash commands.** `init` copies the bundled `commands/*.md` into the project's `.claude/commands/postman/` directory. Each markdown file is a thin Claude Code slash command whose body invokes the matching MCP tool with the user's args. That is what makes `/postman:syncapi`, `/postman:syncchanges`, etc. show up in Claude Code's command list. (Namespace `postman:` comes from the `postman/` subfolder.)

Result: after `init`, opening Claude Code in the project surfaces all six commands, and they are wired to the live server. **No manual config editing by the user, ever.**

### C.3 `init` is idempotent / re-runnable
- Re-running with an existing `postman-mcp.json` → offers to reuse, update the key, or re-pick the collection.
- Re-running re-copies command md files (picks up package upgrades).
- A `postman-mcp doctor` subcommand re-validates: key works (`GET /me`), collection still exists, server registered, commands present — and reports what's broken.

---

## D. Step 3 — Using it inside Claude Code

Once `init` finishes, the user works entirely in Claude Code. The commands (full spec in §10):

| Command | One-liner |
|---|---|
| `/postman:syncapi <fn\|"METHOD /route"\|code> [--into path]` | Sync **one** API. The kernel. |
| `/postman:syncchanges [--last N] [--since ref]` | Sync **what changed** since last sync. Daily driver. |
| `/postman:sync -<file\|module\|dir> [--into path]` | Sync everything in one file/module/dir. |
| `/postman:syncall [--into path]` | Sync the **whole** codebase. First-run / post-refactor. |
| `/postman:createenv [name]` | Generate a Postman environment from code. |
| `/postman:status [--since ref]` | Read-only **drift check**. No writes. |

Every write-capable command shows a **diff first** (§13) and writes only on confirm.

### Typical first run
```
/postman:syncall          → diff of every route → confirm → collection populated
```
### Typical daily run
```
<write code, commit>
/postman:syncchanges      → diff of only what changed → confirm → done
```

---

## E. The setup contract (what "works in all ways" means)

The system is correctly set up when **all** of these hold. `postman-mcp doctor` checks each:

1. `postman-mcp` CLI is on PATH (`postman-mcp version` works).
2. `postman-mcp.json` exists at project root with a valid `collectionId`.
3. The API key resolves from its `apiKeyRef` and `GET /me` returns 200.
4. The MCP server is registered in Claude Code and `postman-mcp serve` boots clean.
5. The six slash-command md files exist under `.claude/commands/postman/`.
6. The target collection exists in Postman (`GET /collections/{uid}` → 200).

Fail any one → `doctor` names it and gives the one command to fix it.

---

# PART II — PRODUCT SPEC (locked from v2.1)

## 1. Problem

API code and Postman drift apart the moment you ship. Every new route, changed body shape, or added error response means going back into Postman by hand — re-typing fields, re-writing example data, re-doing test scripts. The work is mechanical, constant, and easy to skip, so collections rot. A rotten collection is worse than none: teammates trust it, then get burned by a stale endpoint.

The code already contains everything Postman needs — routes, types, middleware, comments. There is no reason a human should be the copy machine between them.

## 2. What we're building

An MCP server for Claude Code that reads your codebase and writes fully-populated Postman requests — body, params, auth, responses, tests, examples — with zero manual fill afterward. Five sync commands cover the range from "one route" to "the whole project," plus supporting commands for setup and inspection.

**The sources of truth are the code (what the API *is*) and Postman (what already *exists*).** A small side-reference file, `postman-mcp.json`, holds only config and the last-update marker — it is not a mirror of everything pushed.

### Thesis to prove first
The five sync commands are **one engine plus five selectors**. The engine does the only hard thing:

> given a pointer to some code → emit a complete Postman request object.

Everything else decides *which* code goes in and *where* it lands (`--into`). **`syncapi` is the kernel** — build and de-risk it first. If pointing at one function and watching a complete request materialize doesn't feel like magic, nothing downstream fixes that.

## 3. Goals & non-goals

**Goals**
- Sync a single route in one command, complete, with no post-sync editing.
- Make the everyday "sync what I changed" command require zero thought.
- Keep token usage low by parsing only changed files and reading just the collection's basic structure — never re-scanning everything.
- Never destroy human work — scripts, manual examples, manual edits survive every sync.
- Never write to Postman without showing what will change first.
- **One-command setup.** From `pip install` to a populated collection in under five minutes, no manual config editing.

**Non-goals (MVP)**
- Environment switching (no `--env`; always reads from code).
- A heavy local mirror of Postman state. The json stays small.
- Being a Postman UI replacement. We write requests; humans still run and explore them.
- Two-way sync. Code is the source of truth for structure.
- Every framework on day one (see phased parser rollout).

## 4. User

A backend developer on an Express / FastAPI / Django / NestJS codebase who keeps **one collection per project** with the same structure across projects, and is tired of being the manual bridge between code and Postman.

---

## 5. System architecture

```
┌────────────────────┐        slash commands        ┌─────────────────────────────┐
│   Claude Code      │  ───────────────────────────▶ │   Postman MCP Server (local)│
│   (the client)     │  ◀─────────────────────────── │   `postman-mcp serve`       │
└────────────────────┘     diffs / prompts / results └──────────────┬──────────────┘
                                                                     │
        ┌────────────────────────────────────────────────────────────┼───────────────┐
        ▼                         ▼                  ▼                 ▼               ▼
   Input resolver            The engine        Postman client     Git reader     Config store
   (OpenAPI spec, else       (request builder) (api.getpostman    (diff since    (postman-mcp.json)
    framework parser)                           .com REST)         commit)
```

**MCP server components**
1. **Command router** — maps a slash command + args to an operation.
2. **Input resolver** — produces a normalized route model from the best available source: OpenAPI spec if one exists, framework code parsing otherwise (§9).
3. **The engine** — turns a route model into a Postman request object (§8).
4. **Postman client** — talks to the Postman REST API (§6); reads the collection's basic structure and writes.
5. **Git reader** — resolves "what changed since X" for `syncchanges`.
6. **Config store** — reads/writes the small `postman-mcp.json` side-reference (§7).
7. **Secret resolver** — reads the API key from its reference; never writes it to disk.

The server runs locally (`postman-mcp serve`), is registered in Claude Code as an MCP server by `init`, and exposes one MCP tool per command in §10.

---

## 6. Authentication & connecting to Postman

### 6.1 How auth works
Postman's REST API lives at `https://api.getpostman.com` and authenticates with a **personal API key** in the `X-Api-Key` header. The MCP server uses that one key for every call.

### 6.2 Where the key lives — never in the repo
The raw key is **never** stored in `postman-mcp.json` (which is committable). It lives in one of, by preference:
1. **OS credential store** (Keychain / Secret Service / Credential Manager) — default.
2. **Environment variable** `POSTMAN_API_KEY` — referenced as `env:POSTMAN_API_KEY`.
3. **Gitignored secret file** `.postman-mcp.secret` — fallback.

The json stores only a pointer: `config.apiKeyRef`. The secret resolver reads the value at run time. The user provides the key themselves in the terminal during `init`; the tool never asks Claude to type it into a web form.

### 6.3 The `init` auth handshake
1. Prompt the user to provide / locate the Postman API key (generated in Postman → Account Settings → API Keys).
2. Validate it: `GET /me`. On 401, stop and explain how to generate a valid key.
3. Enumerate workspaces and collections: `GET /workspaces`, `GET /collections`. The user picks the **project's collection** (or creates one); its id is saved as the default target.
4. Persist workspace, `collectionId`, and `apiKeyRef` to the json.

### 6.4 Postman API surface used
| Operation | Endpoint |
|---|---|
| Validate key | `GET /me` |
| List workspaces / collections | `GET /workspaces`, `GET /collections` |
| Read collection (incl. basic structure) | `GET /collections/{uid}` |
| Write collection | `PUT /collections/{uid}` |
| Create collection | `POST /collections` |
| Create / update environment | `POST /environments`, `PUT /environments/{uid}` |

> **Note on writes:** the public Postman API reads and writes a collection as one whole object — no per-request endpoint. So every write is: read the target collection → find/merge the request (matched by method + path in the live collection) → `PUT` the merged collection. This is why the tool reads the collection's basic structure at sync time instead of trusting a local registry.

---

## 7. The side-reference file — `postman-mcp.json`

Created by `init` at the project root. **Small and stable.** Holds config and a last-update marker only — not a copy of what's been pushed. The tool reads it to know *where* to write (the collection) and *what changed* (the commit), then goes to the code and Postman for everything else.

### Why it's lightweight
- The **code** is the truth for what each API is — so the tool always re-reads the code when adding/updating an API.
- **Postman** is the truth for what exists — so the tool reads the collection's basic structure (folders + each request's method + path) at sync time to find matches, rather than mirroring every `requestId` locally.
- The json therefore never goes stale against Postman, and never bloats. Token cost stays low because `syncchanges` parses only files changed since `lastUpdate.commit`, and the collection read is a single call for basic structure.

### Shape
```json
{
  "version": 1,
  "config": {
    "framework": "fastapi",
    "inputMode": "openapi",
    "openApiSource": "http://localhost:8000/openapi.json",
    "workspace": "<workspace-id>",
    "collectionId": "<collection-uid>",
    "defaultInto": "/",
    "apiKeyRef": "keychain:postman-mcp"
  },
  "lastUpdate": {
    "commit": "a1b2c3d",
    "at": "2026-06-27T10:00:00Z"
  }
}
```

- **config.collectionId** — the project's one collection; the default target for every sync.
- **config.inputMode** — `openapi` or `code`; which source the resolver uses (§9). Re-checked for freshness each sync.
- **config.openApiSource** — file path or URL of the spec, when `inputMode` is `openapi`.
- **config.defaultInto** — default folder path inside that collection when `--into` is omitted.
- **config.apiKeyRef** — reference to the key (never the key).
- **lastUpdate** — last-synced commit + timestamp; powers `syncchanges`' zero-arg default.

**Safe to commit.** No secrets — only a reference and a collection id. Committing it means the team shares the same target config. (Add `.postman-mcp.secret` to `.gitignore` — `init` does this automatically.)

---

## 8. The engine — code → Postman request

Input: one normalized route model (from OpenAPI or code — §9). Output: one complete Postman request object. Pipeline:

1. **Method + URL** — from the route model; `{{base_url}}` prefixes the path; `--into` / `defaultInto` decides the folder.
2. **Params** — path params from the route pattern, query/header params from the signature/decorators.
3. **Request body** — from the body type (Pydantic / Zod / serializer / DTO / TS interface). Each field gets a realistic example from its type and name (`email` → fake email, `amount` → number, `created_at` → ISO date).
4. **Auth headers** — if the route is behind auth middleware, set Bearer `{{token}}` and add the header.
5. **Responses** — one saved response per declared status: all 2xx with real field names from the response model, plus the standard error set (400/401/403/404/422/500) in the framework's error format.
6. **Test scripts** — three tiers: *status* (deterministic), *schema* (deterministic), and *business-logic* (inferred — **the one non-deterministic part**, gated on quality).
7. **Examples** — realistic dummy values for body + params, reused across the request and its saved responses.
8. **Docs** — request description from the code's docstring / comments.

Output conforms to the **Postman Collection v2.1** item schema (`request`, `response[]`, `event[]` for scripts, `description`).

---

## 9. Input resolution — OpenAPI first, code parsing as fallback

The route model can come from two sources. **An OpenAPI spec is always preferred when one exists**, because it is the framework's own declaration of the API — fully typed, complete, and already normalized — so trusting it is both more accurate and far cheaper than re-deriving the same facts from raw source. Code parsing is the fallback for projects (or routes) the spec doesn't cover.

### 9.1 The resolution flow

```
                    ┌─────────────────────┐
                    │  OpenAPI spec        │
                    │  available?          │
                    └──────────┬──────────┘
                       YES     │     NO
                  ┌────────────┘     └────────────┐
                  ▼                               ▼
        ┌───────────────────┐           ┌───────────────────┐
        │ Use OpenAPI       │           │ Parse code         │
        │ → route model     │           │ → route model      │
        │ (typed, complete) │           │ (framework parser) │
        └─────────┬─────────┘           └─────────┬─────────┘
                  └──────────────┬────────────────┘
                                 ▼
                     normalized route model
                  { method, path, pathParams,
                    queryParams, headers, bodyType,
                    responseTypes, authRequired,
                    docstring, codeRef }
                                 ▼
                         the engine (§8)
```

Both paths emit the **same normalized route model**, so the engine and everything downstream is identical regardless of source. The only thing that changes is where the model comes from.

### 9.2 "OpenAPI available?" — how it's decided

In priority order, the resolver looks for a spec:
1. **Explicit path** in config — `config.openApiSource` (a file path or a URL like `http://localhost:8000/openapi.json`). Set at `init` if detected; user can override.
2. **Live framework endpoint** — FastAPI/NestJS serve a spec at a well-known route (`/openapi.json`, `/api-json`). If the app is running, fetch it.
3. **Committed spec file** — `openapi.json` / `openapi.yaml` / `swagger.json` at project root or a conventional location.
4. **Generated on demand** — for frameworks that can emit a spec without a running server (e.g. FastAPI's `app.openapi()`), the resolver can produce one in a short subprocess.

Found at any step → **use OpenAPI**. None found → **parse code**.

`init` records what it found in `config.inputMode` (`openapi` | `code`) and `config.openApiSource`, so every later sync takes the same path without re-deciding from scratch (it still re-checks freshness — a stale or missing spec falls back to code automatically).

### 9.3 Path A — Use OpenAPI

Map the spec straight into the route model:
- `paths.{path}.{method}` → method + path + path/query/header params (`parameters[]`).
- `requestBody.content.*.schema` (resolving `$ref` into `components.schemas`) → `bodyType`.
- `responses.{code}.content.*.schema` → `responseTypes`, one per declared status.
- `security` / `components.securitySchemes` → `authRequired` + the auth header.
- `summary` / `description` → `docstring`.

This path needs **no framework-specific code** — one mapper covers every framework that emits a valid OpenAPI 3.x document. It is the default for FastAPI, NestJS (with `@nestjs/swagger`), and DRF (with `drf-spectacular`).

### 9.4 Path B — Parse code (fallback)

Used when no spec exists — most commonly **Express**, which has no native spec, and any framework where the spec is absent or only partially covers the routes. Per-framework extraction:

| Framework | Routes from | Body / response types from | Auth from |
|---|---|---|---|
| **FastAPI** | `@app.post("/path")` decorators | Pydantic models, `response_model` | `Depends(get_current_user)` |
| **Express** | `app.get/post`, router mounts | JSDoc / inline (weaker — no native types) | auth middleware in the chain |
| **Django (DRF)** | `urls.py` patterns, viewsets | serializers | `permission_classes` |
| **NestJS** | `@Controller` + `@Post()` | DTOs with class-validator | `@UseGuards(AuthGuard)` |

Express has no native type system, so body inference there is best-effort and flagged "lower confidence" in the diff when types are absent. Ambiguous fuzzy targets are never guessed — the parser lists candidates and asks.

**Pydantic v1 vs v2:** the FastAPI code parser supports both. It detects the installed major version and uses the matching introspection API (`model_fields` / `model_json_schema` on v2, `__fields__` / `schema()` on v1). *(Note: when FastAPI serves OpenAPI — Path A — this is moot, since the spec already carries the resolved schema.)*

### 9.5 Per-route mixing

Resolution is per route, not per project. If the OpenAPI spec covers most endpoints but a few are registered in a way the spec misses (a manually mounted Express-style router inside an otherwise FastAPI app, an undocumented route), those individual routes fall back to code parsing while the rest use the spec. The diff (§13) labels each request with its source (`[openapi]` / `[code]`) so lower-confidence ones are visible.

---

## 10. Commands

### 10.1 Core sync commands

#### `/postman:syncapi` — single API *(kernel — build first)*
```
/postman:syncapi <function_name | "METHOD /route" | "pasted code"> [--into path]
```
Most surgical. Target by function name (`createPayment`), route string (`"POST /payments/refund"`), or pasted snippet. Touches nothing else. Diff, then write.

#### `/postman:syncchanges` — sync what changed *(daily driver)*
```
/postman:syncchanges [--last N] [--since commit|date]
```
**Default (no flags): everything changed since `lastUpdate.commit`.** You never name a git ref.
- `--last 3` — last 3 commits (no `HEAD~3` syntax)
- `--since 2026-06-01` / `--since a1b2c3d` — explicit anchor
- First run with no marker → errors gently, suggests `/postman:syncall`

Per change type: **new** → full create · **modified** → only changed structural fields, human-owned scripts/examples preserved · **deleted** → marked deprecated (soft).

#### `/postman:sync -<target>` — file / module / directory
```
/postman:sync -<filename|module|directory> [--into path]
```
Syncs every API in one file/module/directory. Fuzzy-matches; if ambiguous, lists candidates and asks. Never guesses silently.

#### `/postman:syncall` — full codebase
```
/postman:syncall [--into path]
```
Reads every route/controller/model and syncs the lot. For first-time setup or post-refactor. Always diffs first.

#### `/postman:createenv` — generate a Postman environment
```
/postman:createenv [env_name]
```
Creates an environment with dummy variables inferred from code (always from code). Secret-like values (`key`/`token`/`secret`/`password` patterns) are masked and flagged for manual fill. Adds the `{{base_url}}` and `{{token}}` variables the synced requests reference.

### 10.2 Supporting commands

#### `/postman:status` — read-only drift check
```
/postman:status [--since commit|date|last]
```
Shows what *would* sync — new / modified / deprecated routes and anything in the collection that has drifted from code — **without writing**. `syncall`'s diff minus the write.

> **Note:** `init` and `doctor` are **terminal** CLI subcommands (`postman-mcp init`, `postman-mcp doctor`), not slash commands — they run before Claude Code is wired up. All `/postman:*` commands above are the in-Claude-Code surface.

---

## 11. The `--into` flag

Selects the **folder path inside the project's collection** where the API lands.
- Path format: `payments`, `auth/oauth`, `orders/v2/fulfillment`
- Missing folders auto-created
- **Idempotent** — re-running matches the existing request (by method + path) in the live collection and updates it in place, no duplicates
- Omitted → `config.defaultInto`
- Targeting a collection other than the configured default requires `--confirm` *(safety rail; veto if unwanted)*

---

## 12. End-to-end flow — adding an API

`/postman:syncapi createPayment --into payments`

1. **Resolve target** — parser finds `createPayment` in the code → route model.
2. **Parse** — extract method `POST`, path `/payments`, body type, auth middleware, response models, docstring.
3. **Build** — engine assembles the full request object (body example, params, auth header, all responses, tests, examples, docs).
4. **Read collection** — `GET` the project's collection; scan its basic structure for an existing `POST /payments` → not found → it's new. Resolve `--into payments` to the `payments` folder (create it if missing).
5. **Diff** — render the before/after (§13) in Claude Code.
6. **Confirm** — diff always shown; a non-default collection target requires `--confirm`.
7. **Write** — merge the request into the collection JSON, `PUT /collections/{uid}`.
8. **Record** — update `lastUpdate` (commit + timestamp) in the json.

Updating an existing API is identical except step 4 *finds* the request in the live collection → step 7 merges in place. The existing request's test scripts and manual examples are read from Postman and **preserved**; only structural fields change.

---

## 13. Diff preview

Every write is preceded by a diff in Claude Code. Example (new request):

```
SYNC PREVIEW — POST /payments  →  collection / payments   [NEW] [openapi]

+ Request    POST {{base_url}}/payments
+ Auth       Bearer {{token}}              (from require_auth middleware)
+ Body       { "amount": 4200, "currency": "USD", "method": "card" }
+ Responses  201 Created, 400, 401, 422, 500
+ Tests      status(201) · schema(PaymentResponse) · business(amount > 0)
+ Examples   1 success, 4 error

Write? [y / n]
```

Modified requests show field-level `~` changes and explicitly list anything **preserved** (human-owned scripts/examples). Each request is tagged with its source — `[openapi]` or `[code]` — so lower-confidence code-parsed routes are visible at a glance. Nothing writes on `n`.

---

## 14. What every synced API auto-fills

| Field | Source |
|---|---|
| Docs | code comments / docstrings |
| Params | path / query / header |
| Request body | Pydantic / Zod / serializer / DTO / TS types |
| Auth headers | detected from middleware |
| Success responses | all 2xx, real field names |
| Error responses | 400 / 401 / 403 / 404 / 422 / 500 |
| Test scripts | status + schema + business-logic assertions |
| Example data | realistic dummy values from field types |

Every row is deterministic except **business-logic assertions**, the engine's one genuine unknown — gated on quality; status + schema ship first.

---

## 15. Idempotency & conflict policy

**Identity — matched against the live collection, not a local registry.** A route is keyed by `METHOD + normalized path` (`POST:/payments/refund`). `/users/:id`, `/users/{id}`, `/users/<id>` normalize to one route. On sync, the tool reads the collection's basic structure and matches by this key → updates the existing request in place. A rename = soft-delete-old + create-new.

**Conflict rule — code wins on structure, human wins on craft.**
- Code owns: params, body shape, responses, auth headers.
- Human owns: test scripts, manually edited descriptions, manually changed examples. These are **read back from the existing request** during an update and left untouched; only structural fields are overwritten.

---

## 16. Secret handling

- Postman API key: stored by reference only (§6.2); never in the committable json, never in plain text, never typed into a web form by the tool.
- Synced env vars: values matching `key` / `token` / `secret` / `password` patterns are masked (Postman "secret" type) and flagged for manual fill.

---

## 17. Non-negotiable safety rules

- **Diff before every write.** No skip flag.
- **Recovery is re-sync, not rollback.** Because the diff stops bad writes and the code is the source of truth, fixing a mistaken request is just re-running the sync from code. *(No snapshot/rollback system in MVP — flagged; a passive backup can be added later if wanted.)*
- **Writing to a non-default collection requires `--confirm`.**
- **Secrets always masked.**
- **Deletes are soft by default.** `--purge` required for hard delete.

---

## 18. Error handling & edge cases

| Situation | Behavior |
|---|---|
| Invalid / expired API key | Stop, explain how to regenerate; never partial-write |
| Ambiguous fuzzy target | List candidates, ask — never guess |
| Parse failure on a route | Skip it, report it, continue the rest; never write a half-built request |
| Postman API 5xx / rate limit | Retry with backoff; if still failing, abort cleanly with no partial collection write |
| Bad write reaches Postman | Re-sync from code (the source of truth) — no rollback needed |
| Untyped body (Express) | Best-effort body, flagged "lower confidence" in the diff |
| `postman-mcp.json` missing | Any command except `init` errors and tells you to run `postman-mcp init` |
| First `syncchanges`, no marker | Errors gently, suggests `/postman:syncall` |
| Route deleted in code | Soft-deprecate in the collection; `--purge` to hard-delete |
| MCP server not registered | `postman-mcp doctor` detects it and re-runs registration |
| Slash commands missing in Claude Code | `postman-mcp init` (or `doctor`) re-copies the command md files |
| OpenAPI source unreachable / stale | Fall back to code parsing for the affected routes; note the fallback in the diff |
| Spec covers only some routes | Per-route mixing (§9.5) — spec where present, code elsewhere; each request labeled by source |

---

## 19. Build phases

**Phase 0 — Setup spine (Wk 1–2)**
- The package skeleton, `pyproject.toml` entry points, `postman-mcp serve` booting a stub MCP server, `postman-mcp init` writing config + registering with Claude Code + copying command md files, `postman-mcp doctor`. **Prove the full chain end to end with a single dummy tool before building the engine.**

**Phase 1**
- **Wk 3–10** — `syncapi` (kernel, de-risk the engine) with the **OpenAPI path first** (one mapper covers FastAPI/NestJS/DRF), then `syncchanges` + `createenv` + `status`.
- **Wk 11–14** — `sync -file` + the `--into` routing system + the **code-parsing fallback** (Express first, since it has no spec).
- **Wk 15–18** — `syncall` + complete the code parsers (FastAPI, Django, NestJS fallbacks) + per-route mixing.

**Phase 2 (Wk 19–24)** — GitHub Actions / GitLab CI hook, Newman test runner.

**Phase 3 (Wk 25+)** — mock server from schema, pre-commit OWASP security checks, auto-published living docs.

---

## 20. Out of scope (MVP)

Environment switching · rollback / snapshot system · GraphQL sync · gRPC / Protobuf · Postman Flows · real-time collaborative editing · production traffic drift detection.

---

## 21. Success metrics

- **Setup:** `pip install` → populated collection in under 5 minutes, zero manual config editing.
- **Completeness:** ≥80% of synced requests need zero manual edits afterward.
- **Speed:** single new route synced end-to-end in under ~10s.
- **Test trustworthiness:** % of generated tests passing on first run against a live endpoint.
- **Stickiness:** daily-active use of `syncchanges`.
- **Token cost:** avg tokens per `syncchanges` run, trending down.
- **Safety:** zero bad writes reach Postman without first appearing in a diff; zero silent overwrites of human-owned scripts.

---

## 22. Open questions

- Business-logic assertion quality bar — default pass-rate gate vs. behind a flag?
- Renamed-route handling — soft-delete + create for MVP, or true rename detection?
- Concurrent writes — two devs syncing the same collection; last-write-wins is the natural outcome since each reads the live collection first. Acceptable, or add a lightweight lock?
- API-key storage default — **resolved: OS keychain ships first**, env var and secret-file as fallbacks chosen at `init`.
- Pydantic v1 vs v2 — **resolved: both supported via version detection (§9).**

---

## Appendix — Quickstart (the README's first screen)

```bash
# 1. install
pip install postman-mcp

# 2. set up this project (once)
cd my-api-project
postman-mcp init
#   → paste your Postman API key
#   → pick workspace + collection
#   → done: server registered, commands installed

# 3. open Claude Code in this project, then:
/postman:syncall        # first full sync
/postman:syncchanges    # from now on, after each change

# anytime something looks off:
postman-mcp doctor      # checks the whole setup chain
```
