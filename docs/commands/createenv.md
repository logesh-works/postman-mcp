# `/postman:createenv`: generate an environment

Creates a Postman environment with variables inferred from your code, including the
`{{base_url}}` and `{{token}}` variables that synced requests reference.

## Usage

```text
/postman:createenv [env_name]
```

If `env_name` is omitted, a name is generated from your framework, like `fastapi env`.

## What it generates

- `{{base_url}}` and `{{token}}`: the variables every synced request depends on.
- Inferred variables, pulled from headers and query params the parser found in your
  routes. Always from code, never guessed from a running server.

## Secret handling

Any variable whose name matches `key`, `token`, `secret`, or `password` gets stored with
Postman's "secret" type (masked in the UI) and flagged for manual fill. The tool never
invents a secret value.

## Example

```text
/postman:createenv

ENV PREVIEW: "fastapi env"

  base_url = http://localhost:8000
  token = <blank>  (secret, masked, fill manually)

Create this environment in Postman? [y / n]
```

See [secret handling](../architecture/overview.md#safety) for the full policy. Once the
write result is shown, the command ends; no further analysis or follow-on commentary.
