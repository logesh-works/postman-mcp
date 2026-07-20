"""``get_contract`` — the single provider-agnostic bootstrap surface.

Any LLM host that can read JSON Schema and markdown can produce a valid APIM from
this response alone — no provider SDK, no Claude-specific prompt format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ConfigError, load_config
from postman_mcp.contract.schema import (
    APIM_SUPPORTED_MAJORS,
    MAX_DOCUMENT_BYTES,
    MAX_ENDPOINTS,
    MAX_EVIDENCE_PER_FACT,
    export_json_schema,
)
from postman_mcp.contract.sync_schema import export_metadata_schema, export_sync_config_schema

_PLAYBOOK_DIR = Path(__file__).parent / "playbook"
_FRAMEWORK_DIR = _PLAYBOOK_DIR / "frameworks"
_SKILLS_DIR = _PLAYBOOK_DIR / "skills"
_POSTMAN_V21_SCHEMA_URL = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"

CONFIDENCE_REFERENCE = {
    "openapi_verified": 100,
    "ast_verified": 95,
    "framework_verified": 90,
    "multi_source_inferred": 75,
    "ai_inferred": 50,
    "weak_inference": 25,
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def get_contract(version: str = "1") -> dict:
    """Publish the APIM schema, discovery playbook, and framework guides.

    ``version`` selects the requested contract major (only ``"1"`` is currently
    supported). An unsupported major returns an explicit error rather than a silent
    downgrade to whatever the server actually implements.
    """
    requested_major = None
    try:
        requested_major = int(str(version).split(".", 1)[0])
    except (ValueError, TypeError):
        pass
    if requested_major is not None and requested_major not in APIM_SUPPORTED_MAJORS:
        return {
            "error": (
                f"Unsupported contract major {version!r}. "
                f"Supported majors: {list(APIM_SUPPORTED_MAJORS)}."
            ),
            "server_capabilities": {"supported_apim_majors": list(APIM_SUPPORTED_MAJORS)},
        }

    framework_guides = {
        path.stem: _read(path) for path in sorted(_FRAMEWORK_DIR.glob("*.md"))
    }

    return {
        "apim_schema": export_json_schema(),
        "playbook": _read(_PLAYBOOK_DIR / "discovery.md"),
        "framework_guides": framework_guides,
        "confidence_reference": CONFIDENCE_REFERENCE,
        "server_capabilities": {
            "max_endpoints": MAX_ENDPOINTS,
            "max_evidence_per_fact": MAX_EVIDENCE_PER_FACT,
            "max_document_bytes": MAX_DOCUMENT_BYTES,
            "supported_apim_majors": list(APIM_SUPPORTED_MAJORS),
        },
    }


def get_sync_contract(
    skills: Optional[list[str]] = None, project_root: Path | str = "."
) -> dict:
    """Publish everything an LLM needs to drive the file-based sync flow.

    Provider-agnostic bootstrap for the LLM-driven six commands: the cross-cutting
    workflow doc, the individually loadable **skills** (single-responsibility
    discovery/building units a command names a subset of — see each command's `.md`),
    the ``metadata.json``/``sync.config.json`` JSON Schemas, and the Postman Collection
    v2.1 schema URL ``collection.json`` must conform to. The LLM writes ``postman/sync/``
    from this alone; the MCP verifies + syncs. Skills are served here, not as
    Claude-specific ``.claude/skills/`` files, so any MCP-capable LLM gets the exact same
    content — no host-specific mechanism required.

    ``skills`` selects a subset by name (token optimization — ``createenv`` needs 2 of
    10); ``None`` returns everything. ``available_skills`` always lists every name so a
    host can discover what exists cheaply; unknown requested names land in
    ``unknown_skills`` rather than erroring, so a typo never strands a session.
    """
    all_skills = {path.stem: _read(path) for path in sorted(_SKILLS_DIR.glob("*.md"))}
    unknown: list[str] = []
    if skills is None:
        selected = all_skills
    else:
        requested = list(skills)
        selected = {name: all_skills[name] for name in requested if name in all_skills}
        unknown = sorted(set(requested) - set(all_skills))
    try:
        sync_dir = load_config(project_root).config.syncDir
    except ConfigError:
        sync_dir = "postman/sync"  # not yet initialized — report the default
    out = {
        "workflow": _read(_PLAYBOOK_DIR / "workflow.md"),
        "skills": selected,
        "available_skills": sorted(all_skills),
        "collection_schema_url": _POSTMAN_V21_SCHEMA_URL,
        "metadata_schema": export_metadata_schema(),
        "sync_config_schema": export_sync_config_schema(),
        "sync_dir": sync_dir,
        "files": ["collection.json", "metadata.json", "sync.config.json"],
    }
    if unknown:
        out["unknown_skills"] = unknown
    return out
