# Contributing

The full, authoritative contributing guide lives in
[`CONTRIBUTING.md`](https://github.com/logesh-works/postman-mcp/blob/main/CONTRIBUTING.md)
at the repo root. This page is a quick orientation for working on the codebase.

## Setup

```bash
git clone https://github.com/logesh-works/postman-mcp
cd postman-mcp
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS / Linux:        source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

All tests mock the Postman REST API via `respx`. No real API key is needed, and no
network calls are made.

## Where things live

| You want to… | Look in |
|---|---|
| Change how a request is built | `engine/builder.py`, `engine/examples.py`, `engine/tests.py` |
| Improve OpenAPI mapping | `input/openapi.py` |
| Add/fix a framework parser (V2 pipeline) | `input/parsers/` |
| Change matching / merge behavior | `postman/merge.py` |
| Change the diff output | `diff/render.py` |
| Touch a command's orchestration | `service/`, `server.py` |
| Change setup (`init` / `doctor`) | `cli.py`, `setup/` |
| Improve repo indexing | `index/` — see [repository index & retrieval](../architecture/indexing.md) |
| Improve context retrieval | `retrieve/` — same page |

New framework support generally belongs in Claude's own understanding of the
framework, not in a new parser — the seven slash commands work on any framework Claude
can read. A new parser under `input/parsers/` is still worth adding for the
deterministic, LLM-free tool surface described in
[the engineering handoff](../architecture/handoff.md); see that page before starting one.

## Conventions

- **Small, single-responsibility modules.** The hard work is isolated in the engine.
- **Explain the why, not the what.** Comments should capture non-obvious intent or
  constraints. The code already says what it does.
- **Add a test for every behavior change.** Bug fixes get a regression test.
- **Update the docs** in `docs/` when you change a command, flag, or config field, and add
  a `CHANGELOG.md` entry under `## [Unreleased]`.

## Building the docs locally

```bash
pip install -e ".[docs]"
mkdocs serve     # live preview at http://127.0.0.1:8000
mkdocs build --strict   # what CI runs
```

## Adding a new framework parser

1. Create `input/parsers/<framework>.py` implementing the parser interface in
   `input/parsers/base.py`.
2. Emit the same normalized `RouteModel` as every other source. The engine must not need
   to know where the model came from.
3. Register detection in `input/detect.py`.
4. Add a guide under `docs/frameworks/` and a runnable example under `examples/`.
5. Add tests, including a parse-failure case (a route it should skip-and-report, not crash
   on).
