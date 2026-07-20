"""Read/write ``postman/config.json`` — the small, committable, secret-free side-reference.

Holds config + a last-update marker only, never a mirror of what was pushed and
**never a secret** (only ``apiKeyRef``).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

# Everything this tool owns lives under one visible top-level folder: postman/.
# postman/config.json and postman/sync/ are meant to be committed and reviewed;
# postman/secret, postman/index/, postman/models/, postman/plans/, postman/snapshots/,
# and postman/audit.jsonl are internal cache/state (see setup/registration.py's
# ensure_gitignore, which ignores those specifically and not the whole folder).
POSTMAN_DIR = "postman"
CONFIG_FILENAME = f"{POSTMAN_DIR}/config.json"
SECRET_FILENAME = f"{POSTMAN_DIR}/secret"

# Pre-reorg locations, kept only so _migrate_legacy_layout can find and move them.
_LEGACY_CONFIG_FILENAME = "postman-mcp.json"
_LEGACY_SECRET_FILENAME = ".postman-mcp.secret"
_LEGACY_CACHE_DIR = ".postman-mcp"


class ConfigError(Exception):
    """Raised when config is missing/invalid."""


class ConfidencePolicyConfig(BaseModel):
    """Gate thresholds for the submitted-model pipeline — safe defaults, all overridable."""

    autoThreshold: int = 90
    flagThreshold: int = 75
    approvalThreshold: int = 50


class ProjectConfig(BaseModel):
    """The ``config`` block of ``postman/config.json``."""

    framework: Optional[str] = None
    inputMode: str = "openapi"  # "openapi" | "code"
    # V2→V3 migration flag (see docs/architecture/v3-proposal.md). "v2" = parser
    # pipeline (current default) · "v3" = index/retrieval pipeline (Phase 2+).
    # Phase 0 introduces the flag only; no behavior switches on it yet.
    engine: str = "v2"
    openApiSource: Optional[str] = None
    workspace: Optional[str] = None
    collectionId: Optional[str] = None
    # The Postman environment this project last created/updated (createenv/sync_env) —
    # the "configured reference" that makes re-running createenv idempotent: found by
    # this id first, so a later rename of environment.json's name still updates the
    # same environment instead of creating a duplicate.
    environmentId: Optional[str] = None
    defaultInto: str = "/"
    # Directory the LLM-driven flow writes its artifacts to (collection.json,
    # metadata.json, sync.config.json). Committable, git-diffable, regenerable.
    syncDir: str = "postman/sync"
    apiKeyRef: str = "keychain:postman-mcp"  # reference only, never the key
    # Output shaping (owner preference; reversible):
    generateTests: bool = False  # add status/schema test scripts to requests
    # "single" = 1 best response only (default) · "minimal" = 1 success + 1 error ·
    # "full" = every declared 2xx + standard errors
    responseStyle: str = "single"

    # Submitted-model pipeline config. Read only by the get_contract/submit_model/
    # plan/apply tool surface (service/aiplan.py) — the six original commands
    # (service/sync.py) don't consult any of these.
    confidencePolicy: ConfidencePolicyConfig = Field(default_factory=ConfidencePolicyConfig)
    allowLowConfidence: bool = False  # required to sync anything below the approval floor
    writeProtection: str = "normal"  # "normal" | "readonly" | "approve-all"
    planTtlHours: float = 24.0


class LastUpdate(BaseModel):
    """Last-synced marker powering ``syncchanges`` zero-arg default."""

    commit: Optional[str] = None
    at: Optional[str] = None


class PostmanMcpConfig(BaseModel):
    """The full ``postman/config.json`` document."""

    version: int = 1
    config: ProjectConfig = Field(default_factory=ProjectConfig)
    lastUpdate: LastUpdate = Field(default_factory=LastUpdate)

    def mark_synced(self, commit: Optional[str]) -> None:
        self.lastUpdate = LastUpdate(
            commit=commit,
            at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


def _migrate_legacy_layout(project_root: Path | str = ".") -> None:
    """Move pre-reorg files/dirs into ``postman/`` (idempotent, best-effort).

    Older installs scattered their state at repo root (``postman-mcp.json``,
    ``.postman-mcp.secret``, ``.postman-mcp/``). Run automatically on every config
    read so existing projects pick up the new layout without a manual step.
    """
    root = Path(project_root)

    legacy_config = root / _LEGACY_CONFIG_FILENAME
    new_config = root / CONFIG_FILENAME
    if legacy_config.exists() and not new_config.exists():
        new_config.parent.mkdir(parents=True, exist_ok=True)
        legacy_config.rename(new_config)

    legacy_secret = root / _LEGACY_SECRET_FILENAME
    new_secret = root / SECRET_FILENAME
    if legacy_secret.exists() and not new_secret.exists():
        new_secret.parent.mkdir(parents=True, exist_ok=True)
        legacy_secret.rename(new_secret)

    legacy_cache = root / _LEGACY_CACHE_DIR
    if legacy_cache.is_dir():
        for name in ("index", "models", "plans", "snapshots"):
            src, dst = legacy_cache / name, root / POSTMAN_DIR / name
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
        audit_src = legacy_cache / "audit.jsonl"
        audit_dst = root / POSTMAN_DIR / "audit.jsonl"
        if audit_src.exists() and not audit_dst.exists():
            audit_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(audit_src), str(audit_dst))
        try:
            legacy_cache.rmdir()  # only succeeds once empty
        except OSError:
            pass


def config_path(project_root: Path | str = ".") -> Path:
    _migrate_legacy_layout(project_root)
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cfg.model_dump(), indent=2) + "\n", encoding="utf-8"
    )
    return path
