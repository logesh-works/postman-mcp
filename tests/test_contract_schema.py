"""The APIM v1 schema — round-trip, size caps, and the CI schema-drift check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from postman_mcp.contract.publish import get_contract
from postman_mcp.contract.schema import (
    ApiModel,
    Endpoint,
    Evidence,
    ExtractionMethod,
    GeneratorInfo,
    MAX_ENDPOINTS,
    MAX_EVIDENCE_PER_FACT,
    apim_major,
    export_json_schema,
)
from postman_mcp.model.store import ModelIngestError, parse_model


def _endpoint(uid="default:GET:/x", path="/x") -> Endpoint:
    return Endpoint(
        uid=uid, service="default", method="GET", path=path,
        identity_evidence=[Evidence(file="app.py", line_start=1, line_end=1, symbol="x",
                                     extraction_method=ExtractionMethod.AI_INFERRED,
                                     snippet_sha256="a" * 64, quote="@app.get('/x')")],
    )


def test_apim_major_parsing():
    assert apim_major("1.0") == 1
    assert apim_major("2.3") == 2
    assert apim_major("garbage") is None
    assert apim_major(None) is None


def test_minimal_model_round_trips():
    model = ApiModel(generator=GeneratorInfo(provider="claude"), endpoints=[_endpoint()])
    dumped = model.model_dump(mode="json", by_alias=True)
    restored = ApiModel.model_validate(dumped)
    assert restored.endpoints[0].uid == "default:GET:/x"


def test_schema_json_snapshot_matches_generated():
    """CI schema-drift check — the checked-in snapshot must match schema.py."""
    snapshot_path = Path(__file__).parent.parent / "postman_mcp" / "contract" / "schema.json"
    on_disk = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert on_disk == export_json_schema(), (
        "contract/schema.json is stale — regenerate it from postman_mcp.contract.schema."
    )


def test_get_contract_publishes_schema_and_playbook():
    contract = get_contract("1")
    assert "apim_schema" in contract
    assert "playbook" in contract and "evidence" in contract["playbook"].lower()
    assert "fastapi" in contract["framework_guides"]
    assert contract["confidence_reference"]["openapi_verified"] == 100


def test_get_contract_rejects_unsupported_major():
    contract = get_contract("99")
    assert "error" in contract


def test_endpoint_count_cap_blocks_model():
    endpoints = [_endpoint(uid=f"default:GET:/x{i}", path=f"/x{i}") for i in range(MAX_ENDPOINTS + 1)]
    raw = ApiModel(generator=GeneratorInfo(provider="claude"), endpoints=endpoints).model_dump(mode="json")
    with pytest.raises(ModelIngestError):
        parse_model(raw)


def test_evidence_per_fact_cap_blocks_model():
    ep = _endpoint()
    ep.identity_evidence = [
        Evidence(file="app.py", line_start=1, line_end=1, symbol="x", snippet_sha256="a" * 64)
        for _ in range(MAX_EVIDENCE_PER_FACT + 1)
    ]
    raw = ApiModel(generator=GeneratorInfo(provider="claude"), endpoints=[ep]).model_dump(mode="json")
    with pytest.raises(ModelIngestError):
        parse_model(raw)


def test_unsupported_apim_major_blocks_model():
    raw = ApiModel(generator=GeneratorInfo(provider="claude")).model_dump(mode="json")
    raw["apim_version"] = "99.0"
    with pytest.raises(ModelIngestError):
        parse_model(raw)


def test_malformed_json_blocks_model():
    with pytest.raises(ModelIngestError):
        parse_model("{not valid json")


def test_schema_violation_blocks_model():
    with pytest.raises(ModelIngestError):
        parse_model({"apim_version": "1.0", "endpoints": [{"method": "GET"}]})  # missing uid/path
