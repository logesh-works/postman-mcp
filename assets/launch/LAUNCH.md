# Launch assets

Copy-ready text for publishing Postman MCP. Tune the voice per platform, but keep the
core fact the same: it generates and updates Postman requests from your API code, and
shows a diff before every write.

> **Before posting anything here:** re-confirm the
> [release checklist](../../docs/development/release-process.md) against the tag you're
> actually announcing (CI green, changelog updated, tag published to PyPI).

## Messaging guardrails

The architecture is two clean layers — **Claude does the reading and reasoning; the MCP
server does the checking and writing** — and the messaging should reflect that, in plain,
precise language. No hype, no "AI-powered"/"next-generation" framing.

- ✅ Use: **"Generates and updates Postman requests from your API code, from inside
  Claude Code"** or **"Claude-guided, but deterministic."**
- ✅ Fine to highlight `/postman:prompt` as a way to steer a sync in plain English —
  "the instruction shapes what Claude writes; the MCP server stays deterministic and
  verifies it before anything reaches Postman."
- ❌ Avoid: **"AI inside MCP,"** "the MCP server uses AI/an LLM," or anything implying the
  server interprets prompts or runs a model. It does not.
- ❌ Avoid exaggerated claims — "revolutionary," "magic," "next-generation." The pitch is
  precise and practical: it reads your code and saves you from retyping it into Postman.

---

## PyPI description (short)

> An MCP server for Claude Code that generates and updates Postman requests from your
> API code, with a diff before every write.

(The long description is the rendered `README.md`.)

## GitHub "About" section

> Generates and updates Postman requests from your API code, from inside Claude Code.

**Website:** https://logesh-works.github.io/postman-mcp/

## GitHub Topics

```
postman, mcp, model-context-protocol, claude-code, openapi, api, fastapi,
django, express, nestjs, api-testing, developer-tools, python, automation,
api-documentation
```

---

## Hacker News (Show HN)

**Title:**
`Show HN: Postman MCP, syncs your API code into Postman from Claude Code`

**Body:**

> I kept manually re-typing the same information into Postman that already existed in my
> code: request bodies, example values, test assertions. Every time a route changed, the
> Postman collection didn't, until someone noticed and fixed it by hand. So I built
> something to read the code directly and write the Postman request for me.
>
> Postman MCP is an MCP server for Claude Code that reads your codebase and writes
> complete Postman requests: body, params, auth headers, a response, realistic example
> values, and optionally a test script. Seven commands cover everything from one route
> (`/postman:syncapi`) to the whole project (`/postman:syncall`), plus natural-language
> sync, environments, and a read-only drift check.
>
> A few choices I'd like feedback on:
> - **OpenAPI-first.** When your framework emits a spec (FastAPI, NestJS, DRF), one
>   mapper handles all of them. No spec, like with Express? It falls back to parsing
>   your code directly, and labels each request `[openapi]` or `[code]` so you can see
>   which confidence level you're getting.
> - **A diff before every write, no flag to skip it.** Nothing reaches Postman until
>   you've seen exactly what's about to change.
> - **It doesn't destroy your work.** Hand-written test scripts and edited examples are
>   read back and kept on every sync; only the structural fields get overwritten from
>   code.
> - **Secrets never touch the repo.** The Postman API key is stored by reference (OS
>   keychain, env var, or a gitignored file), never written into committed config.
>
> `pip install postman-mcp`, then `postman-mcp init`, then use the `/postman:*` commands
> in Claude Code. MIT licensed. Repo and docs in the first comment. What would make you
> trust a tool like this to write to your own collections?

## Reddit (r/Python, r/webdev, r/django, r/node)

**Title:**
`I built an MCP server that generates Postman requests from your API code`

**Body:**

> If you maintain a Postman collection for a real project, you know how this goes: a
> route changes, the collection doesn't, and a teammate gets burned by a stale endpoint a
> few weeks later. Updating it by hand is pure busywork since the information already
> exists in the code.
>
> Postman MCP reads your code and generates complete Postman requests (body, params,
> auth, a response, examples, and optionally test scripts) from inside Claude Code. It
> uses your framework's OpenAPI spec when there is one (FastAPI, NestJS, DRF) and falls
> back to parsing the code directly when there isn't (Express, mainly). It shows a diff
> before every write, and your hand-written test scripts survive every sync instead of
> getting overwritten.
>
> ```bash
> pip install postman-mcp
> postman-mcp init
> # then in Claude Code:
> /postman:syncall
> ```
>
> It's open source (MIT). Repo: https://github.com/logesh-works/postman-mcp, docs:
> https://logesh-works.github.io/postman-mcp/. Honest feedback welcome, especially on the
> framework parsers and whether the safety model actually holds up.

*(Per subreddit: lead with the relevant framework, DRF for r/django, Express/Nest for
r/node, and read each subreddit's self-promotion rules first.)*

## LinkedIn

> **Your Postman collection goes stale the moment you ship. I built something to fix
> that.**
>
> API code and Postman drift apart constantly. Every new route or changed body means
> going back into Postman by hand to keep it current. Nobody does this consistently,
> because it's pure busywork, so collections rot and teammates stop trusting them.
>
> So I built Postman MCP: an open-source MCP server for Claude Code that reads your
> codebase and writes complete Postman requests (body, params, auth, responses,
> examples, and tests) without you typing any of it by hand.
>
> What it does:
> - Uses your framework's OpenAPI spec when there is one, and falls back to parsing the
>   code directly when there isn't.
> - Shows a diff before every write. No flag to skip it.
> - Keeps your hand-written tests and examples across every sync instead of overwriting
>   them.
> - Never writes secrets into the repo.
>
> `pip install postman-mcp`, run `postman-mcp init`, then drive it from Claude Code.
>
> MIT licensed. Repo and docs in the comments. I'd love feedback from anyone who
> maintains API collections at scale.
>
> \#Python #API #Postman #DeveloperTools #OpenSource #MCP

## X / Twitter (thread starter)

> Your Postman collection goes stale the moment you ship.
>
> Postman MCP reads your API code and writes complete Postman requests (body, params,
> auth, responses, tests, examples) from Claude Code. No manual typing. A diff before
> every write.
>
> `pip install postman-mcp`

**Follow-up tweet:**

> It's Claude-guided, but deterministic. Steer a sync in plain English —
> `/postman:prompt "Act as a Stripe API architect"` — and Claude shapes the framing.
> The MCP server itself runs no LLM: it validates and verifies whatever Claude wrote
> before anything reaches Postman.

---

## Launch checklist

- [ ] A live `init` → `syncall` run against a real Postman workspace. See release-process.md.
- [ ] Latest release published to PyPI and installable (`pip install postman-mcp`)
- [ ] Docs site live on GitHub Pages
- [ ] Social preview image set on the repo
- [ ] Animated demo embedded in the README
- [ ] GitHub About and Topics set
- [ ] README badges all green (CI, PyPI, license, docs)
- [ ] Post to HN, Reddit, LinkedIn, X (stagger them, engage with replies)
