# Repository index and context retrieval

Two packages back the discovery step every slash command starts with:
`postman_mcp/index/` and `postman_mcp/retrieve/`, exposed as the `index()` and
`context()` MCP tools. Neither is a slash command — they're primitives Claude calls
directly while reading your project, in place of reading files unbounded.

Both packages are zero-LLM, framework-blind, and cheap: everything in them is either a
file-system scan, a language-grammar parse, or a graph walk. No package here knows what
FastAPI, Django, or NestJS is — framework interpretation stays with Claude; the index
only tells it where to look.

## `index()` — the deterministic repo map

```text
index(refresh: bool = False) -> str
```

Builds (or refreshes) the repo index, a five-part picture of the project:

- **Scanner** (`scanner.py`) — a git-aware, ignore-aware file inventory. Prefers
  `git ls-files` (exact `.gitignore` semantics); falls back to a walk with a
  conservative ignore list outside a git repo. Every file gets a SHA-256, which is the
  cache invalidation key for everything downstream.
- **Symbols** (`symbols.py`) — every class/function/method, with decorators, base
  classes, and line spans. Python uses the stdlib `ast` module; other languages use a
  built-in regex backend, with an optional tree-sitter backend available via the
  `treesitter` extra.
- **Graph** (`graph.py`) — an import graph with per-language resolution (Python module
  rules, Node relative-path rules) plus a name-resolution query surface (`resolve_name`,
  `importers_of`) the retrieval layer runs on.
- **Services** (`services.py`) — service-unit discovery from build manifests
  (`pyproject.toml`, `package.json` workspaces, `pom.xml`, `go.mod`, ...): a unit is "a
  directory with a manifest," nothing framework-specific.
- **Corpus** (`corpus.py`) — an evidence harvest of independent, human-authored API
  witnesses: OpenAPI documents, `.http`/`.rest` files, URL literals in test files,
  existing Postman collections. Used by retrieval as corroborating context, and by
  verification to help ground claims.

Everything is content-addressed, so an unchanged file is never re-parsed on the next
call — `index()` on a large, mostly-untouched repo is near-instant. Its output is a
compact repo map — services, language counts, files with decorated symbols, and the
corpus summary — meant to orient Claude before it calls `context()` per endpoint, not to
be read in full by a human.

## `context(target, budget=8000)` — the graph-sliced bundle

```text
context(target: str, budget: int = 8000) -> str
```

`target` is a handler/symbol name, a file path, `"file.py::symbol"`, or
`"METHOD /path"`. The slicer (`retrieve/slicer.py`) resolves it to one or more seed
symbols, then walks the graph outward in priority order:

1. **seed** — the handler itself (decorators included)
2. **type closure** — DTO/model classes referenced from the seed, expanded recursively
   (nested models, base classes), depth-limited
3. **call closure** — one hop into service functions the handler calls
4. **mount chain** — lines in files that import the seed's file (router registration,
   prefixes) — this is how `"POST /api/users"` finds a handler whose own decorator only
   says `"/users"`
5. **witnesses** — matching entries from the evidence corpus (a test that calls this
   route, an `.http` request, an OpenAPI path)

Chunks are always whole symbols — a class or function is never split — headed with
`## file:start-end [role]` so the returned text is pre-anchored: the citations a synced
endpoint needs are exactly the chunk headers, not a guess. The budgeter fits chunks into
the token budget rank-by-rank, always keeping the seed even if it alone exceeds budget,
and lists what got cut so Claude can request it explicitly instead of inventing its
contents.

If `context()` can't resolve a target — an unusual mount style, a framework it hasn't
seen — Claude falls back to reading the repository directly with its own tools; the
citation rules still apply either way.

## Why this replaces reading the repo freely

Grepping for framework patterns and following imports by hand scales tokens with how
much gets read, which scales with repository size and search discipline. `context()`
scales with the *target*: one endpoint's bundle costs a few thousand tokens whether the
repository has 500 files or 50,000, because the graph already knows what matters before
Claude asks.

## Where this fits

`index()`/`context()` back discovery for every slash command and for the lower-level
`get_contract`/`submit_model` tool surface described in
[the engineering handoff](handoff.md). Two real import-resolution bugs were found and
fixed while building the retrieval benchmark that validates this: package-then-submodule
Python imports (`from pkg import submodule`) not resolving to the submodule file, and
`from x import Y as Z` aliasing breaking both mount-chain discovery and type resolution
wherever a file used the alias. `ImportEdge` now carries both `names` (definition-site)
and `used_as` (alias-aware, as referenced at the call site).
