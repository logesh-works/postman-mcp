"""Secret manager — the API key lives by reference, never in the repo (PRD §6.2, §16).

Three locations, by preference:
1. OS credential store via ``keyring`` (default)   → ``keychain:<name>``
2. Environment variable                            → ``env:POSTMAN_API_KEY``
3. Gitignored secret file ``.postman-mcp.secret``  → ``file:.postman-mcp.secret``

``postman-mcp.json`` stores only the *reference* (``config.apiKeyRef``); this module
resolves the value at run time and writes the raw key only to keychain/env/file.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

KEYRING_SERVICE = "postman-mcp"


class SecretError(Exception):
    """Raised when the key cannot be resolved from its reference (PRD §18)."""


def _keyring():
    """Import keyring lazily so a missing backend doesn't break import-time."""
    import keyring  # type: ignore

    return keyring


def store_api_key(ref: str, key: str, project_root: Path | str = ".") -> None:
    """Persist the raw key to the location named by ``ref`` (PRD §6.2).

    Never writes to ``postman-mcp.json``. For ``env:`` refs the caller is responsible
    for exporting the variable; we just validate the shape.
    """
    scheme, _, target = ref.partition(":")
    if scheme == "keychain":
        _keyring().set_password(KEYRING_SERVICE, target or KEYRING_SERVICE, key)
    elif scheme == "file":
        path = Path(project_root) / (target or ".postman-mcp.secret")
        path.write_text(key.strip() + "\n", encoding="utf-8")
    elif scheme == "env":
        # Cannot persist an env var for the user's shell; document the expectation.
        os.environ[target or "POSTMAN_API_KEY"] = key
    else:  # pragma: no cover - guarded at call sites
        raise SecretError(f"Unknown apiKeyRef scheme: {scheme!r}")


def resolve_api_key(ref: str, project_root: Path | str = ".") -> str:
    """Read the raw key for ``ref``. Raises :class:`SecretError` if unresolvable."""
    scheme, _, target = ref.partition(":")
    if scheme == "keychain":
        try:
            value = _keyring().get_password(KEYRING_SERVICE, target or KEYRING_SERVICE)
        except Exception as exc:  # pragma: no cover - backend specific
            raise SecretError(f"keyring backend error: {exc}") from exc
        if not value:
            raise SecretError(
                "No key found in OS credential store. Re-run `postman-mcp init`."
            )
        return value
    if scheme == "env":
        value = os.environ.get(target or "POSTMAN_API_KEY")
        if not value:
            raise SecretError(
                f"Environment variable {target or 'POSTMAN_API_KEY'} is not set."
            )
        return value
    if scheme == "file":
        path = Path(project_root) / (target or ".postman-mcp.secret")
        if not path.exists():
            raise SecretError(f"Secret file {path} not found.")
        return path.read_text(encoding="utf-8").strip()
    raise SecretError(f"Unknown apiKeyRef scheme: {scheme!r}")


# Values matching these patterns are masked in generated environments (PRD §16).
_SECRET_PATTERN = re.compile(r"(key|token|secret|password)", re.IGNORECASE)


def mask_if_secret(name: str) -> bool:
    """True when an env-var name looks secret and must be masked/flagged (PRD §16)."""
    return bool(_SECRET_PATTERN.search(name))
