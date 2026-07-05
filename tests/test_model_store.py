"""Model Ingestor & Store — canonicalization, content-addressing, persistence."""

from __future__ import annotations

from postman_mcp.contract.schema import ApiModel, Endpoint, Evidence, GeneratorInfo
from postman_mcp.model.store import compute_model_id, load_model, save_model


def _model() -> ApiModel:
    ep = Endpoint(
        uid="default:GET:/x", service="default", method="GET", path="/x",
        identity_evidence=[Evidence(file="app.py", line_start=1, line_end=1, snippet_sha256="a" * 64)],
    )
    return ApiModel(generator=GeneratorInfo(provider="claude"), endpoints=[ep])


def test_save_and_load_round_trip(tmp_path):
    model_id, saved = save_model(_model(), tmp_path)
    assert model_id.startswith("sha256:")
    loaded = load_model(model_id, tmp_path)
    assert loaded.endpoints[0].uid == saved.endpoints[0].uid


def test_resubmission_is_idempotent(tmp_path):
    id1, _ = save_model(_model(), tmp_path)
    id2, _ = save_model(_model(), tmp_path)
    assert id1 == id2


def test_model_id_is_content_addressed():
    a = compute_model_id(_model())
    m2 = _model()
    m2.endpoints[0].uid = "default:GET:/y"
    m2.endpoints[0].path = "/y"
    b = compute_model_id(m2)
    assert a != b


def test_model_id_stable_across_key_order(tmp_path):
    """Canonical JSON sorts keys — dict construction order must not affect the id."""
    m1 = _model()
    m2 = ApiModel.model_validate(m1.model_dump(mode="json"))  # re-parse, same content
    assert compute_model_id(m1) == compute_model_id(m2)
