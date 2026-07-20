"""Model Ingestor & Store — accept, canonicalize, content-address, persist.

A model's ``model_id`` is the SHA-256 of its canonical JSON (sorted keys, ``\\n``-free
compact separators, UTF-8) — stable across producers and operating systems, and
idempotent: resubmitting an identical analysis is a no-op that resolves to the same id.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import ValidationError

from postman_mcp.contract.schema import (
    MAX_DOCUMENT_BYTES,
    MAX_ENDPOINTS,
    MAX_EVIDENCE_PER_FACT,
    APIM_SUPPORTED_MAJORS,
    ApiModel,
    apim_major,
)

MODELS_DIRNAME = "postman/models"


class ModelIngestError(Exception):
    """The document itself is unusable — corresponds to a BLOCK_MODEL verdict."""


def _models_dir(project_root: Path | str) -> Path:
    d = Path(project_root) / MODELS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def canonical_json_bytes(model: ApiModel) -> bytes:
    """Deterministic serialization used both for hashing and for on-disk storage."""
    data = model.model_dump(mode="json", by_alias=True)
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_model_id(model: ApiModel) -> str:
    digest = hashlib.sha256(canonical_json_bytes(model)).hexdigest()
    return f"sha256:{digest}"


def _model_id_filename(model_id: str) -> str:
    return model_id.split(":", 1)[-1] + ".json"


def _check_size_caps(raw: Union[dict, str, bytes]) -> None:
    if isinstance(raw, (dict, list)):
        size = len(json.dumps(raw))
    elif isinstance(raw, bytes):
        size = len(raw)
    else:
        size = len(raw.encode("utf-8"))
    if size > MAX_DOCUMENT_BYTES:
        raise ModelIngestError(
            f"Model document is {size} bytes, exceeding the {MAX_DOCUMENT_BYTES}-byte cap."
        )


def parse_model(raw: Union[dict, str, bytes]) -> ApiModel:
    """Validate a raw APIM document (dict, JSON text, or bytes) — check V-01.

    Raises :class:`ModelIngestError` for anything that makes the document itself
    unusable: malformed JSON, schema violations, unsupported contract major, or a
    size cap breach. Never partially accepts a document.
    """
    _check_size_caps(raw)
    if isinstance(raw, (bytes, str)):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ModelIngestError(f"Model document is not valid JSON: {exc}") from exc
    else:
        data = raw

    version = data.get("apim_version") if isinstance(data, dict) else None
    major = apim_major(version) if version is not None else 1
    if major is not None and major not in APIM_SUPPORTED_MAJORS:
        raise ModelIngestError(
            f"Unsupported apim_version {version!r}. Supported majors: "
            f"{list(APIM_SUPPORTED_MAJORS)}."
        )

    try:
        model = ApiModel.model_validate(data)
    except ValidationError as exc:
        raise ModelIngestError(f"Model failed schema validation: {exc}") from exc

    if len(model.endpoints) > MAX_ENDPOINTS:
        raise ModelIngestError(
            f"Model declares {len(model.endpoints)} endpoints, exceeding the "
            f"{MAX_ENDPOINTS}-endpoint cap."
        )
    for ep in model.endpoints:
        for facts in (
            ep.identity_evidence,
            *(t.evidence for t in _all_traced(ep)),
        ):
            if len(facts) > MAX_EVIDENCE_PER_FACT:
                raise ModelIngestError(
                    f"Endpoint {ep.uid!r} has a fact with {len(facts)} evidence items, "
                    f"exceeding the {MAX_EVIDENCE_PER_FACT}-item cap."
                )
    return model


def _all_traced(ep) -> list:
    """Every ``Traced`` field on an endpoint, for the evidence-count cap check."""
    out = []
    for field in (ep.operation_id, ep.summary, ep.description, ep.tags, ep.folder,
                  ep.deprecated, ep.request_body, ep.auth, ep.examples, ep.versioning):
        if field is not None:
            out.append(field)
    out.extend(ep.path_params)
    out.extend(ep.query_params)
    out.extend(ep.headers)
    out.extend(ep.responses)
    return out


def save_model(
    raw: Union[dict, str, bytes, ApiModel], project_root: Path | str = "."
) -> tuple[str, ApiModel]:
    """Parse (if needed), canonicalize, content-address, and atomically persist.

    Returns ``(model_id, model)``. Resubmitting byte-identical content is idempotent —
    it re-derives and overwrites the same file, changing nothing observable.
    """
    model = raw if isinstance(raw, ApiModel) else parse_model(raw)
    model_id = compute_model_id(model)
    path = _models_dir(project_root) / _model_id_filename(model_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(canonical_json_bytes(model))
    tmp.replace(path)
    return model_id, model


def load_model(model_id: str, project_root: Path | str = ".") -> ApiModel:
    path = _models_dir(project_root) / _model_id_filename(model_id)
    if not path.exists():
        raise ModelIngestError(f"No stored model with id {model_id!r}.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ApiModel.model_validate(data)


def load_model_from_path(path: Path | str) -> ApiModel:
    """Read and validate an APIM document an LLM wrote to disk with its own tools."""
    p = Path(path)
    if not p.exists():
        raise ModelIngestError(f"Model file not found: {p}")
    return parse_model(p.read_text(encoding="utf-8"))


def _report_path(model_id: str, project_root: Path | str) -> Path:
    return _models_dir(project_root) / f"{model_id.split(':', 1)[-1]}.report.json"


def save_report(model_id: str, report_json: str, project_root: Path | str = ".") -> None:
    path = _report_path(model_id, project_root)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(report_json, encoding="utf-8")
    tmp.replace(path)


def load_report_json(model_id: str, project_root: Path | str = ".") -> Optional[str]:
    path = _report_path(model_id, project_root)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
