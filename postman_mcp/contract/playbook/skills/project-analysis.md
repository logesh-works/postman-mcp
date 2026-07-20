# Skill: Project Analysis

**Responsibility:** determine the scope of code to analyze for this command, and the
service/monorepo boundaries within it. Nothing else — route/auth/DTO discovery are
separate skills that run after this one establishes scope.

## Determining scope

The command name tells you the scope:

| Command | Scope |
|---|---|
| `syncall` | The whole repository. |
| `syncapi <target>` | The single endpoint named — a function/handler name, `"METHOD /path"`, or a pasted code snippet. |
| `sync <file/dir>` | Every endpoint inside that one file, module, or directory. |
| `syncchanges` | Endpoints whose source file changed since the last sync. Run `git diff --name-only <since>..HEAD` (or the equivalent for the range given) to get the file list; `<since>` defaults to the commit recorded by the last sync if the user gave none. |
| `status` | Same scope as `syncall` (or a narrower `--since` range if given) — discovery is identical, only the write step differs (never confirm). |
| `prompt "<instruction>"` | Infer scope from the instruction's wording — one endpoint, one file/dir, changed files, or everything. If ambiguous, ask the user before analyzing anything. |
| `createenv` | The whole repository, but only for environment-relevant signals — see the `environment-discovery` skill, not this one, for what to look for. |

Never widen scope beyond what's asked (e.g. don't re-analyze the whole repo for
`syncapi`) and never narrow it silently (e.g. don't skip a file `syncchanges` says
changed just because it looks unrelated).

## Orient cheaply: call `index()` first

Once per session, call the MCP's **`index()`** tool before opening any file. It returns a
deterministic repo map — services (from build manifests), language counts, and which
files contain decorated symbols (the likely handlers/DTOs) — for one or two thousand
tokens instead of an exploratory read of the tree. Use it to decide *where* the scope's
code lives; the per-endpoint reading itself then goes through `context()` (see
`api-discovery`).

## Service / monorepo boundaries

Before discovering routes, identify whether the repository is:
- **A single service** — most repos. Proceed directly.
- **A monorepo with multiple services** (multiple `package.json`/`pyproject.toml`/`go.mod`
  etc. at different roots, or an Nx/Turborepo/Lerna workspace). Determine which
  service(s) the requested scope actually touches — a `syncapi`/`sync` scope should only
  ever analyze the service(s) containing the target, never the whole monorepo.

## What you're establishing for later skills

By the end of this skill you should know: which files to read, and — if a monorepo — which
service each belongs to (relevant to `sync.config.json`'s notes if it affects
interpretation). You are not yet finding routes, auth, or DTOs; that's
`api-discovery`/`auth-discovery`/`dto-discovery`.
