# Example: Spring (Boot)

A minimal Spring Boot payments controller. `server.servlet.context-path=/api` in
`application.properties` is read and prepended to every route — the class-level
`@RequestMapping("/payments")` alone would only give you `/payments`, not the real
`/api/payments` the app actually serves.

## The API

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| `POST` | `/api/payments` | — | `PaymentRequest` | Create a payment |
| `GET` | `/api/payments/{id}` | — | — | Fetch one |
| `DELETE` | `/api/payments/{id}` | — | — | Refund |

No auth column has a checkmark here on purpose: Spring Security is normally configured
centrally rather than per-controller, so the parser doesn't attempt to detect it (see
the [framework guide](https://logesh-works.github.io/postman-mcp/frameworks/spring/)) —
every route parses as unauthenticated regardless of what's actually enforced at runtime.

## Run it

This is a source-only example — there's no `pom.xml`/`build.gradle` here, since Postman
MCP never imports or runs your project, only reads the source with a regex-based parser.
Point `postman-mcp init` at this directory (or your own Spring project) directly:

```bash
postman-mcp init
```

## Sync it

In Claude Code, in this directory:

```text
/postman:syncapi create --into payments
```

Actual diff preview:

```text
Collection: <your collection>
Plan: 1 new · 0 modified

[NEW] POST /api/payments   → payments   ✓ verified (PaymentController.java:14)

Write to Postman? Re-run with confirm=true to apply.   (nothing writes on n)
```

Add the auth header by hand after syncing, or via `/postman:prompt "add a bearer token
header to the payments routes"`, if your controller is actually behind Spring Security.

The real generated Collection v2.1 items are checked in under
[`expected-output/`](expected-output/):
[`post-api-payments.item.json`](expected-output/post-api-payments.item.json),
[`get-api-payments-id.item.json`](expected-output/get-api-payments-id.item.json), and
[`delete-api-payments-id.item.json`](expected-output/delete-api-payments-id.item.json).
