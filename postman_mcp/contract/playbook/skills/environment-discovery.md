# Skill: Environment Discovery

**Responsibility:** for `createenv`, find the environment variables a Postman
environment should define, and write `postman/sync/environment.json`. Unlike the other
skills, this one doesn't need `api-discovery`/`dto-discovery`/etc. — it's a standalone
skill for a standalone command.

## What to look for

- **Base URL(s)**: how the app's own dev/local server is configured (a default port, a
  `HOST`/`PORT` env var, a config file value). Always include `base_url`.
- **Auth tokens**: whatever the synced requests' `auth` blocks reference (`{{token}}` by
  convention — always include a `token` variable).
- **API keys / secrets**: third-party API keys, database credentials, signing secrets —
  anything the code reads from environment variables or a secrets manager that a
  developer would need to supply to actually run requests against this API.
- **Other config-driven values** the requests depend on (a tenant ID, an API version
  segment, a feature-flag header) if you noticed them during analysis.

Do not invent variables nothing in the code suggests exist.

## Shape of `postman/sync/environment.json`

```json
{
  "name": "<framework/project> env",
  "values": [
    { "key": "base_url", "value": "http://localhost:8000", "type": "default", "enabled": true },
    { "key": "token", "value": "", "type": "secret", "enabled": true },
    { "key": "stripe_api_key", "value": "", "type": "secret", "enabled": true }
  ]
}
```

- **`type: "secret"`** for anything secret-like (`key`/`token`/`secret`/`password`/api
  keys) — Postman masks these in its UI. Leave the `value` blank for the user to fill in
  manually; never guess or fabricate a real-looking secret value.
- **`type: "default"`** for non-secret values (like `base_url`) — a real, usable default
  is fine here (e.g. the port the code's own dev-server config uses).
- Always include `base_url` and `token`, even if you can't find explicit evidence for
  `token` beyond "the requests use bearer auth" — it's the variable those requests
  reference, so it belongs in the environment regardless.

## Workflow

1. Call `get_sync_contract()`, load this skill + `project-analysis`.
2. Analyze the project for the signals above.
3. Write `postman/sync/environment.json`.
4. Call `sync_env` with `confirm: false` — shows a preview, writes nothing.
5. Ask "Create this environment in Postman? [y/n]"; only on yes, call `sync_env` again
   with `confirm: true`.
