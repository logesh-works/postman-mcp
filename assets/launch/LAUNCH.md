# Launch assets

Copy-ready text for publishing Postman MCP. Tune voice per platform; keep the core promise
identical: **sync API code into Postman with zero manual fill, diff before every write.**

> ⚠️ **Pre-launch gate:** do not post any of these until the
> [release gates](../../docs/development/release-process.md) are met — a real test suite
> (>80% coverage) and a validated live `init → syncall` run. Launching on top of the
> currently-missing test suite would burn the one first impression.

---

## PyPI description (short)

> An MCP server for Claude Code that syncs your API code into Postman collections —
> body, params, auth, responses, tests, and examples — with zero manual fill. OpenAPI-first,
> code-parsing fallback, and a diff before every write.

(The long description is the rendered `README.md`.)

## GitHub "About" section

> Sync your API code into Postman collections from Claude Code — OpenAPI-first, zero manual
> fill, diff before every write.

**Website:** https://logesh-works.github.io/postman-mcp/

## GitHub Topics

```
postman · mcp · model-context-protocol · claude-code · openapi · api · fastapi ·
django · express · nestjs · api-testing · developer-tools · python · automation ·
api-documentation
```

---

## Hacker News (Show HN)

**Title:**
`Show HN: Postman MCP – sync your API code into Postman from Claude Code, zero manual fill`

**Body:**

> I got tired of being the manual copy machine between my API code and Postman. Every new
> route or changed body meant re-typing fields, re-writing example data, and re-doing test
> scripts by hand — so my collections always rotted.
>
> Postman MCP is an MCP server for Claude Code that reads your codebase and writes
> fully-populated Postman requests: body, params, auth headers, every response, realistic
> examples, and a test scaffold. Five sync commands cover the range from one route
> (`/postman:syncapi`) to the whole project (`/postman:syncall`).
>
> Design choices I'd love feedback on:
> - **OpenAPI-first.** When your framework emits a spec (FastAPI, NestJS, DRF), one mapper
>   handles all of them. No spec (e.g. Express)? It falls back to parsing your code, and
>   labels each request `[openapi]` or `[code]` so you can see the confidence.
> - **Diff before every write — no skip flag.** Nothing reaches Postman until you've seen
>   exactly what changes.
> - **It never destroys your work.** Hand-written test scripts and edited examples are read
>   back and preserved on every sync; only structural fields are overwritten from code.
> - **Secrets never touch the repo.** The Postman API key is stored by reference (OS
>   keychain / env / gitignored file).
>
> `pip install postman-mcp` → `postman-mcp init` → use the `/postman:*` commands in Claude
> Code. MIT licensed. Repo + docs in the first comment. What would make you trust a tool
> like this to write to your collections?

## Reddit (r/Python, r/webdev, r/django, r/node)

**Title:**
`I built an MCP server that syncs your API code into Postman — zero manual fill, diff before every write`

**Body:**

> If you keep a Postman collection per project, you know the pain: every route change means
> manually re-typing bodies, examples, and tests, so the collection drifts and teammates
> get burned by stale endpoints.
>
> **Postman MCP** reads your code and generates complete Postman requests — body, params,
> auth, all responses, examples, and test scaffolds — from Claude Code. It's OpenAPI-first
> (FastAPI / NestJS / DRF) with a code-parsing fallback (Express + the rest), and it shows
> a diff before every write so nothing happens by surprise. Your hand-written test scripts
> are preserved across syncs.
>
> ```bash
> pip install postman-mcp
> postman-mcp init
> # then in Claude Code:
> /postman:syncall
> ```
>
> It's open source (MIT). Repo: https://github.com/logesh-works/postman-mcp — docs:
> https://logesh-works.github.io/postman-mcp/ . Honest feedback welcome, especially on the
> framework parsers and the safety model.

*(Per-subreddit: lead with the relevant framework — DRF for r/django, Express/Nest for
r/node — and read each subreddit's self-promotion rules first.)*

## LinkedIn

> **Your Postman collection rots the moment you ship. I built something to fix that.**
>
> API code and Postman drift apart constantly — every new route or changed body means
> going back into Postman by hand. The work is mechanical, easy to skip, and the result is
> a collection nobody trusts.
>
> So I built **Postman MCP**: an open-source MCP server for Claude Code that reads your
> codebase and writes fully-populated Postman requests — body, params, auth, responses,
> examples, and tests — with zero manual fill.
>
> → OpenAPI-first, with a code-parsing fallback for frameworks without a spec
> → A diff before every write (no surprises reaching your collection)
> → Your hand-written tests and examples are preserved on every sync
> → Secrets never touch the repo
>
> `pip install postman-mcp`, run `postman-mcp init`, then drive it from Claude Code.
>
> MIT licensed. Repo and docs in the comments. I'd love feedback from anyone who maintains
> API collections at scale.
>
> \#Python #API #Postman #DeveloperTools #OpenSource #MCP

## X / Twitter (thread starter)

> Your Postman collection rots the moment you ship.
>
> Postman MCP reads your API code and writes complete Postman requests — body, params,
> auth, responses, tests, examples — from Claude Code. Zero manual fill. Diff before every
> write.
>
> `pip install postman-mcp` 🧵👇

---

## Launch checklist

- [ ] Release gates met (tests + live run) — see release-process.md
- [ ] `0.1.0` published to PyPI and installable (`pip install postman-mcp`)
- [ ] Docs site live on GitHub Pages
- [ ] Social preview image set on the repo
- [ ] Animated demo embedded in the README
- [ ] GitHub About + Topics set
- [ ] README badges all green (CI, PyPI, license, coverage)
- [ ] Post to HN / Reddit / LinkedIn / X (stagger, engage with replies)
