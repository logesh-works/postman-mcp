# Security Policy

## Supported Versions

Security fixes are applied to the latest released minor version. See
[SUPPORTED_VERSIONS.md](SUPPORTED_VERSIONS.md) for the full support matrix.

| Version | Supported |
|---|---|
| latest `0.x` | ✅ |
| older `0.x`  | ❌ (please upgrade) |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, use one of:

1. **GitHub private vulnerability reporting** — the preferred channel:
   [Report a vulnerability](https://github.com/logesh-works/postman-mcp/security/advisories/new).
2. **Email** — **logeshkumar.dev@gmail.com** with the details below.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (a minimal proof of concept is ideal).
- The version of `postman-mcp` and your OS / Python version.
- Any suggested remediation, if you have one.

You can expect an acknowledgement within **3 business days** and a status update within
**10 business days**. We will coordinate a disclosure timeline with you and credit you in
the release notes unless you prefer to remain anonymous.

## Security Model — what to keep in mind

Postman MCP is designed so that **secrets never enter the repository**:

- The Postman API key is stored **by reference** — in the OS credential store
  (default), an environment variable, or a gitignored `.postman-mcp.secret` file. It is
  **never** written into the committable `postman-mcp.json`.
- The tool **never** asks Claude to type the key into a web form; the key is read
  directly from the terminal by the CLI during `postman-mcp init`.
- Synced environment variables whose names match `key` / `token` / `secret` / `password`
  patterns are masked (Postman "secret" type) and flagged for manual fill.
- **Every write to Postman is preceded by a diff** and writes only on confirmation —
  there is no skip flag.

If you find a way to make a secret leak into a committed file, a write to reach Postman
without a diff, or the key to be transmitted anywhere other than `api.getpostman.com`,
that is a security issue — please report it via the channels above.
