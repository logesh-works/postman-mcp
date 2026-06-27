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

While the project is pre-1.0, only the **latest released `0.x` version** receives bug
and security fixes. Upgrading to the latest patch is the supported path.

After `1.0.0`, this project will follow semantic versioning and maintain the current and
previous minor versions for security fixes. The matrix here will be updated at that time.

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
