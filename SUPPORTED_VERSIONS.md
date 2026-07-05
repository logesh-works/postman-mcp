# Supported Versions

## Python

Postman MCP supports **Python 3.10, 3.11, 3.12, and 3.13**. The minimum is set in
`pyproject.toml` (`requires-python = ">=3.10"`). Each supported version is exercised in
CI on Linux, macOS, and Windows.

| Python | Status |
|---|---|
| 3.13 | ✅ Supported |
| 3.12 | ✅ Supported |
| 3.11 | ✅ Supported |
| 3.10 | ✅ Supported (minimum) |
| ≤ 3.9 | ❌ Not supported |

## Release support

As of `1.0.0`, this project follows Semantic Versioning: the **current minor version**
receives security fixes. Upgrading to the latest patch within the supported line is the
recommended path.

| Version | Status |
|---|---|
| `2.0.x` | ✅ Supported |
| `1.1.x` | ❌ Not supported (superseded by `2.0.0`) |
| `1.0.x` | ❌ Not supported (superseded) |
| `0.1.x` | ❌ Not supported (superseded) |

## Operating systems

| OS | Status |
|---|---|
| Linux | ✅ Tested in CI |
| macOS | ✅ Tested in CI |
| Windows | ✅ Tested in CI |

The OS credential store backend used for the default API-key storage is platform
specific (Keychain on macOS, Secret Service on Linux, Credential Manager on Windows) and
is provided by [`keyring`](https://pypi.org/project/keyring/). When no backend is
available, `postman-mcp init` offers the environment-variable or secret-file fallback.
