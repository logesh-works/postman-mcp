"""``get_contract`` — the single provider-agnostic bootstrap surface.

Any LLM host that can read JSON Schema and markdown can produce a valid APIM from
this response alone — no provider SDK, no Claude-specific prompt format.
"""

from __future__ import annotations

from pathlib import Path

from postman_mcp.contract.schema import (
    APIM_SUPPORTED_MAJORS,
    MAX_DOCUMENT_BYTES,
    MAX_ENDPOINTS,
    MAX_EVIDENCE_PER_FACT,
    export_json_schema,
)

_PLAYBOOK_DIR = Path(__file__).parent / "playbook"
_FRAMEWORK_DIR = _PLAYBOOK_DIR / "frameworks"

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
