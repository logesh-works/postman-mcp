# Custom / unlisted framework discovery guide

No parser exists for this framework, so there is no independent witness to cross-check
your model — every fact you submit is capped at `ai_inferred` (50) for
existence/path unless your identity evidence passes the plausibility check, which can
lift it to `framework_verified` (90) on audited registration-site evidence alone.

Look for the framework's own idiom of:

- a **router/app object** that routes are registered against,
- a **decorator or method call** that binds an HTTP method + path to a handler,
- a **mount/include mechanism** that composes prefixes across files,
- a **body-typing convention** (a validation library, a typed parameter, or plain
  runtime access to the raw request body),
- an **auth convention** (middleware, a decorator, or a guard/interceptor pattern).

Cite the actual registration call for every endpoint — a hallucinated custom-framework
endpoint has no witness engine to catch it except the evidence hash audit, so citation
accuracy matters even more here than for a supported framework. When you can't find a
registration site for something you suspect is an endpoint, leave it out rather than
guessing; a false negative is recoverable (the user can point you at it), a
hallucinated endpoint erodes trust in the whole sync.
