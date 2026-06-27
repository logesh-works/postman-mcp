# Contributing to Postman MCP

Thanks for taking the time to contribute. Postman MCP is an open-source MCP server
that syncs API code into Postman collections. This guide gets you from a fresh clone to
a green test run and a clean pull request.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating you
agree to uphold it. Report unacceptable behavior to the address listed there.

## Ways to contribute

- **Report a bug** — open a [bug report](https://github.com/logesh-works/postman-mcp/issues/new?template=bug_report.yml).
- **Request a feature** — open a [feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml).
- **Improve docs** — everything under `docs/` is fair game; small fixes can go straight to a PR.
- **Add framework coverage** — new or better parsers under `postman_mcp/input/parsers/`.
- **Write tests** — coverage gaps are tracked in [ROADMAP.md](ROADMAP.md) and issues.

## Development setup

Requires **Python ≥ 3.10** and `git` on your PATH.

```bash
git clone https://github.com/logesh-works/postman-mcp
cd postman-mcp

python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# macOS / Linux:        source .venv/bin/activate

pip install -e ".[dev]"
```

This installs the package in editable mode plus the dev tools (`pytest`, `pytest-cov`,
`respx`). After install, `postman-mcp version` should print the current version.

## Running the checks

```bash
pytest                 # run the test suite
pytest --cov           # with coverage (target: >80%)
```

All tests mock the Postman REST API via `respx` — **no real Postman API key is needed**
and no network calls are made. Never commit a real API key or a populated
`postman-mcp.json` / `.postman-mcp.secret`.

## Architecture in one paragraph

The five sync commands are **one engine plus five selectors**. The engine
(`engine/builder.py`) turns a normalized `RouteModel` into a Postman Collection v2.1
item. The input resolver (`input/resolver.py`) produces that `RouteModel` from the best
available source — an OpenAPI spec when one exists, framework code parsing otherwise.
The service layer (`service/`) orchestrates read → diff → confirm → write against the
Postman client (`postman/`). See [docs/architecture/overview.md](docs/architecture/overview.md)
for the full picture, and `docs/implementation-plan.md` for the design rationale.

## Pull request guidelines

1. **Branch** from `main`: `git checkout -b fix/short-description`.
2. **Keep PRs focused** — one logical change. Unrelated cleanups go in their own PR.
3. **Add tests** for any behavior change. Bug fixes should include a regression test.
4. **Update docs** when you change a command, flag, or config field.
5. **Update [CHANGELOG.md](CHANGELOG.md)** under the `## [Unreleased]` heading.
6. **Match the surrounding style** — the code favors small, single-responsibility modules
   and comments that cite the relevant PRD section (e.g. `# PRD §9.3`).
7. Fill out the PR template; link the issue your PR closes.

A maintainer will review. CI must be green before merge.

## Commit messages

Use clear, present-tense summaries (`Add NestJS guard detection`, not `added stuff`).
Reference issues with `Fixes #123` where applicable. Conventional Commits prefixes
(`feat:`, `fix:`, `docs:`, `test:`, `refactor:`) are welcome but not required.

## Reporting security issues

**Do not** open a public issue for security vulnerabilities. Follow
[SECURITY.md](SECURITY.md).
