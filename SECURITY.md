# Security Policy

## Supported Versions

Security fixes are applied to the latest released minor version. See
[SUPPORTED_VERSIONS.md](SUPPORTED_VERSIONS.md) for the full support matrix.

| Version | Supported |
|---|---|
| latest `0.x` | yes |
| older `0.x`  | no, please upgrade |

## Reporting a Vulnerability

Please do not report security vulnerabilities through public GitHub issues.

Instead, use one of these:

1. **GitHub private vulnerability reporting** (preferred):
   [Report a vulnerability](https://github.com/logesh-works/postman-mcp/security/advisories/new).
2. **Email**: logeshkumar.dev@gmail.com, with the details below.

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce it (a minimal proof of concept is ideal).
- The version of `postman-mcp` and your OS/Python version.
- A suggested fix, if you have one.

You can expect an acknowledgement within 3 business days and a status update within 10
business days. We'll coordinate a disclosure timeline with you and credit you in the
release notes unless you'd rather stay anonymous.

## What the security model actually relies on

Postman MCP is built so secrets never enter the repository:

- The Postman API key is stored by reference: in the OS credential store by default, or
  an environment variable, or a gitignored `.postman-mcp.secret` file. It's never
  written into the committable `postman-mcp.json`.
- The tool never asks Claude to type the key into a web form. The key is read directly
  from the terminal by the CLI during `postman-mcp init`.
- Synced environment variables whose names match `key`, `token`, `secret`, or `password`
  are masked using Postman's "secret" type and flagged for manual fill.
- Every write to Postman is preceded by a diff and only happens on confirmation. There's
  no flag that skips this.

If you find a way to make a secret leak into a committed file, a write reach Postman
without a diff first, or the key get transmitted anywhere other than
`api.getpostman.com`, that's a security issue. Please report it through the channels
above.
