"""Shared sync context — config + authenticated client + live collection (PRD §6, §12).

Centralizes the "read the live collection" step (PRD §6.4) so every command matches
against current Postman state rather than a local registry (§15).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from postman_mcp.config.store import PostmanMcpConfig, load_config
from postman_mcp.postman.client import PostmanClient
from postman_mcp.secrets.manager import resolve_api_key


@dataclass
class SyncContext:
    config: PostmanMcpConfig
    client: PostmanClient
    collection: dict[str, Any]
    project_root: Path

    @property
    def collection_id(self) -> str:
        return self.config.config.collectionId or ""

    @property
    def collection_name(self) -> Optional[str]:
        return (self.collection.get("info") or {}).get("name")


def load_context(project_root: Path | str = ".") -> SyncContext:
    """Load config, resolve the key, and read the live target collection (PRD §6.4)."""
    root = Path(project_root)
    config = load_config(root)
    if not config.config.collectionId:
        from postman_mcp.config.store import ConfigError

        raise ConfigError("No collectionId in postman-mcp.json. Run `postman-mcp init`.")
    key = resolve_api_key(config.config.apiKeyRef, root)
    client = PostmanClient(key)
    collection = client.get_collection(config.config.collectionId)
    return SyncContext(config=config, client=client, collection=collection, project_root=root)
