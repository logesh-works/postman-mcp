# `/postman:createenv` — generate an environment

Creates a Postman **environment** with variables inferred from your code, including the
`{{base_url}}` and `{{token}}` variables that synced requests reference.

## Usage

```text
/postman:createenv [env_name]
```

If `env_name` is omitted, a sensible default name is used.

## What it generates

- **`{{base_url}}`** and **`{{token}}`** — the variables every synced request depends on.
- **Inferred variables** — pulled from configuration and code (always from code, never
  guessed from a running server).

## Secret handling

Values whose names match `key` / `token` / `secret` / `password` patterns are:

- stored with Postman's **"secret"** variable type (masked), and
- **flagged for manual fill** — the tool never invents secret values.

## Example

```text
/postman:createenv "Acme — Local"

CREATE ENV PREVIEW — "Acme — Local"
+ base_url   http://localhost:8000
+ token      <secret — fill manually>
+ api_key    <secret — fill manually>

Write? [y / n]
```

See [secret handling](../architecture/overview.md#safety) for the full policy.
