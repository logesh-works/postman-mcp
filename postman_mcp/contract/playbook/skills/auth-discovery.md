# Skill: Authentication Discovery

**Responsibility:** for each endpoint found by `api-discovery`, determine whether auth is
enforced and *where that's proven in code*. Feeds the `auth` claim in `metadata.json`
(see `metadata-builder` for the exact shape).

## Finding where auth is enforced

Look for whatever your framework uses to gate a route behind auth: a guard
(`@UseGuards(AuthGuard)`), a decorator (`@login_required`, `@requires_auth`), middleware
applied at the router/app level, a dependency (`Depends(get_current_user)`), or an
annotation (`@PreAuthorize`, `@Secured`). This can apply at the individual route, the
controller/class, or globally (app-level middleware covering everything unless
overridden) — check all three levels; a route with no per-route guard may still require
auth via a class- or app-level one.

## What to cite

Cite the **exact line** that enforces auth for this specific endpoint — the guard
decorator, the middleware registration, or the dependency parameter. If auth comes from a
class- or app-level source rather than the route itself, cite *that* source line (it's
still real, verifiable evidence) rather than inventing a route-level citation that
doesn't exist.

## When you can't find one

Not every endpoint has auth, and not every auth mechanism is staticaly visible (e.g. auth
enforced entirely by an API gateway in front of the service). **Do not cite something
that isn't really there.** If you can't find genuine evidence either way, omit the `auth`
claim entirely — the endpoint will show as auth-unverified in the diff, which is honest.
A fabricated auth citation gets caught (it won't hash-match) and excludes the whole
endpoint from the sync — worse than just leaving it unverified.

## Scheme

If auth is enforced, name the scheme as best you can tell from the code: `"bearer"`
(JWT/token in header — the common case), `"basic"`, `"apikey"`, `"oauth2"`, `"session"`,
or `"custom"` if none of those fit. Default to `"bearer"` only if the code doesn't make
the scheme clear but auth is clearly required.
