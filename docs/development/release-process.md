# Release process

Releases are automated. Tagging a GitHub Release triggers a build and a publish to PyPI
via OIDC trusted publishing, so no API token needs to be stored in the repo.

## Versioning

Semantic Versioning, in effect as of `1.0.0`: breaking changes require a major version
bump; minor versions are additive; patch versions are bug fixes only.

See [CHANGELOG.md](https://github.com/logesh-works/postman-mcp/blob/main/CHANGELOG.md)
for what shipped in each release, and the [roadmap](../roadmap.md) for what's next.

## Cutting a release

1. **Green CI on `main`.** All tests pass across the OS × Python matrix.
2. **Bump the version** in `pyproject.toml` (`project.version`).
3. **Update `CHANGELOG.md`.** Move `## [Unreleased]` items under a new
   `## [x.y.z] - YYYY-MM-DD` heading, then update the compare links at the bottom.
4. **Commit and tag:**
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag vX.Y.Z
   git push && git push --tags
   ```
5. **Publish a GitHub Release** for the tag. Write release notes for the page — a
   concise summary and highlights aimed at someone deciding whether to upgrade, not a
   verbatim copy of the changelog section.
6. The **Release workflow** (`.github/workflows/release.yml`) builds the sdist + wheel,
   runs `twine check`, and publishes to PyPI.
7. The **Docs workflow** redeploys the site on the next push to `main`.

## First-time PyPI setup

Trusted publishing must be configured once on PyPI:

1. Create the `postman-mcp` project (or reserve the name with a first manual upload).
2. Add a **trusted publisher** for the GitHub repo + the `Release` workflow + the `pypi`
   environment.
3. Create a GitHub Environment named `pypi` (optionally with required reviewers).

After that, every published Release deploys automatically.

## Pre-release checklist

- [ ] `pytest --cov` ≥ 80% locally and in CI
- [ ] `mkdocs build --strict` passes
- [ ] `python -m build && twine check dist/*` clean
- [ ] `CHANGELOG.md` updated
- [ ] README badges and quickstart still accurate
- [ ] A real end-to-end `init` → `syncall` run against a live Postman workspace
