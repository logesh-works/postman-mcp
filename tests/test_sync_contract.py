"""``get_sync_contract`` — the model-agnostic bootstrap for the file-based sync flow."""

from __future__ import annotations

from postman_mcp.contract.publish import get_sync_contract
from postman_mcp.contract.sync_schema import SyncMetadata


_EXPECTED_SKILLS = {
    "project-analysis", "api-discovery", "auth-discovery", "dto-discovery",
    "request-builder", "response-builder", "folder-builder", "collection-builder",
    "metadata-builder", "environment-discovery",
}


def test_sync_contract_publishes_workflow_and_schemas():
    c = get_sync_contract()
    assert "postman/sync" in c["workflow"]
    assert c["collection_schema_url"].startswith("https://schema.getpostman.com")
    assert c["sync_dir"] == "postman/sync"
    assert set(c["files"]) == {"collection.json", "metadata.json", "sync.config.json"}


def test_sync_contract_publishes_all_skills_non_empty():
    c = get_sync_contract()
    assert set(c["skills"]) == _EXPECTED_SKILLS
    for name, content in c["skills"].items():
        assert content.strip(), f"skill {name!r} is empty"
        assert "Responsibility" in content, f"skill {name!r} should state its single responsibility"


def test_sync_contract_selective_skills_returns_only_requested():
    c = get_sync_contract(skills=["project-analysis", "environment-discovery"])
    assert set(c["skills"]) == {"project-analysis", "environment-discovery"}
    # Discovery of the full catalog stays cheap and always available.
    assert set(c["available_skills"]) == _EXPECTED_SKILLS
    assert "unknown_skills" not in c


def test_sync_contract_unknown_skill_names_never_error():
    c = get_sync_contract(skills=["project-analysis", "not-a-real-skill"])
    assert set(c["skills"]) == {"project-analysis"}
    assert c["unknown_skills"] == ["not-a-real-skill"]


def test_metadata_schema_matches_the_model():
    c = get_sync_contract()
    # The published schema is generated from the same Pydantic model the MCP validates
    # against — so it can never drift from what filesync actually enforces.
    assert c["metadata_schema"] == SyncMetadata.model_json_schema()


def test_metadata_model_round_trips_a_realistic_document():
    doc = {
        "endpoints": [
            {"key": "POST:/api/users",
             "citations": [{"file": "a.ts", "line_start": 1, "line_end": 2, "symbol": "create"}],
             "body": {"dto": {"file": "dto.ts", "line_start": 1, "line_end": 3, "symbol": "Dto"},
                      "fields": ["email"]},
             "responses": [{"dto": {"file": "out.ts", "line_start": 1, "line_end": 4}, "fields": ["id"]}]}
        ]
    }
    m = SyncMetadata.model_validate(doc)
    assert m.by_key()["POST:/api/users"].body.fields == ["email"]
