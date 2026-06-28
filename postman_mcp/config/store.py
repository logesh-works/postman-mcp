"""Read/write ``postman-mcp.json`` — the small, committable, secret-free side-reference.

Holds config + a last-update marker only, never a mirror of what was pushed and
**never a secret** (only ``apiKeyRef``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

CONFIG_FILENAME = "postman-mcp.json"
SECRET_FILENAME = ".postman-mcp.secret"


class ConfigError(Exception):
    """Raised when config is missing/invalid."""


class ProjectConfig(BaseModel):
    """The ``config`` block of ``postman-mcp.json``."""

    framework: Optional[str] = None
    inputMode: str = "openapi"  # "openapi" | "code"
    openApiSource: Optional[str] = None
    workspace: Optional[str] = None
    collectionId: Optional[str] = None
    defaultInto: str = "/"
    apiKeyRef: str = "keychain:postman-mcp"  # reference only, never the key
    # Output shaping (owner preference; reversible):
    generateTests: bool = False  # add status/schema test scripts to requests
    # "single" = 1 best response only (default) · "minimal" = 1 success + 1 error ·
    # "full" = every declared 2xx + standard errors
    responseStyle: str = "single"


class LastUpdate(BaseModel):
    """Last-synced marker powering ``syncchanges`` zero-arg default."""

    commit: Optional[str] = None
    at: Optional[str] = None


class PostmanMcpConfig(BaseModel):
    """The full ``postman-mcp.json`` document."""

    version: int = 1
    config: ProjectConfig = Field(default_factory=ProjectConfig)
    lastUpdate: LastUpdate = Field(default_factory=LastUpdate)

    def mark_synced(self, commit: Optional[str]) -> None:
        self.lastUpdate = LastUpdate(
            commit=commit,
            at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


def config_path(project_root: Path | str = ".") -> Path:
    return Path(project_root) / CONFIG_FILENAME


def load_config(project_root: Path | str = ".") -> PostmanMcpConfig:
    """Load and validate config. Raises :class:`ConfigError` if absent."""
    path = config_path(project_root)
    if not path.exists():
        raise ConfigError(
            f"{CONFIG_FILENAME} not found. Run `postman-mcp init` first."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"{CONFIG_FILENAME} is not valid JSON: {exc}") from exc
    return PostmanMcpConfig.model_validate(data)


def save_config(cfg: PostmanMcpConfig, project_root: Path | str = ".") -> Path:
    """Write config as pretty, stable JSON (committable)."""
    path = config_path(project_root)
    path.write_text(
        json.dumps(cfg.model_dump(), indent=2) + "\n", encoding="utf-8"
    )
    return path
