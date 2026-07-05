"""Build a :class:`WitnessSet` from the existing parsers, and convert it to an API model.

Two entry points:

- :func:`build_witness_set` — runs OpenAPI-first + code-parser resolution exactly as
  the legacy commands always have (:func:`postman_mcp.input.resolver.resolve_routes`),
  and returns it keyed for the verification pipeline's cross-checks.
- :func:`witness_to_apim` — mechanically converts a :class:`WitnessSet` into a valid
  :class:`~postman_mcp.contract.schema.ApiModel`, with real evidence (a real file, a
  real cited line, a real SHA-256 of what's actually there). The submitted-model
  ``plan`` tool (``service/aiplan.py``) uses this as its fallback producer when no
  ``model_id`` is given, feeding it through the same verify → plan → apply pipeline an
  LLM-submitted model goes through. The six original commands (``syncapi``/``sync``/
  ``syncall``/``syncchanges``/``createenv``/``status``, in ``service/sync.py``) do
  **not** go through this — they build, diff, and write directly, unchanged.

Known limitation: the existing parsers don't track the source line of each route's
registration site, only ``code_ref`` (``"file"`` or ``"file::symbol"``). Evidence line
numbers here are located by a best-effort text search for the symbol/path in the cited
file — real content, real hash, but not necessarily the exact decorator line. Adding
line-tracking to the parsers themselves would tighten this; out of scope for now since
it doesn't change any parser's routing logic (no new framework intelligence here).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ProjectConfig
from postman_mcp.contract.schema import (
    ApiModel,
    Auth,
    Body,
    Endpoint,
    Evidence,
    ExtractionMethod,
    GeneratorInfo,
    ParamValue,
    RepoInfo,
    ResponseValue,
    SchemaNode,
    Service,
    Traced,
)
from postman_mcp.input.detect import detect_framework
from postman_mcp.input.resolver import resolve_routes
from postman_mcp.models import BodyField, BodyModel, FieldType, InputSource, RouteModel, normalize_path


class WitnessSet:
    """The parsers' independent route set — an oracle for the verification pipeline.

    Keyed by ``uid`` (``"{service}:{METHOD}:{normalized path}"``), matching how the
    verification pipeline recomputes APIM endpoint identity.
    """

    def __init__(
        self,
        routes: list[RouteModel],
        notes: list[str],
        skipped: list[str],
        *,
        service: str = "default",
    ) -> None:
        self.routes = routes
        self.notes = notes
        self.skipped = skipped
        self.service = service
        self.by_uid: dict[str, RouteModel] = {
            f"{service}:{r.key}": r for r in routes
        }

    def get(self, uid: str) -> Optional[RouteModel]:
        return self.by_uid.get(uid)

    def get_by_method_path(self, service: str, method: str, path: str) -> Optional[RouteModel]:
        return self.by_uid.get(f"{service}:{method.upper()}:{normalize_path(path)}")


def build_witness_set(
    project_root: Path | str = ".",
    config: Optional[ProjectConfig] = None,
    *,
    only_files: Optional[list[str]] = None,
    service: str = "default",
) -> WitnessSet:
    """Run the existing OpenAPI-first + code-parser resolution as an independent oracle."""
    cfg = config
    if cfg is None:
        cfg = ProjectConfig(framework=detect_framework(project_root))
    elif cfg.framework is None:
        cfg = cfg.model_copy(update={"framework": detect_framework(project_root)})
    result = resolve_routes(cfg, project_root, only_files=only_files)
    return WitnessSet(result.routes, result.notes, result.skipped, service=service)


# --- witness -> APIM conversion (the fallback extraction engine) ---------------------


def _normalize_snippet(lines: list[str]) -> str:
    return "\n".join(line.rstrip() for line in lines)


def _hash_snippet(lines: list[str]) -> str:
    return hashlib.sha256(_normalize_snippet(lines).encode("utf-8")).hexdigest()


def _locate_evidence(
    project_root: Path, rel_file: str, symbol: Optional[str]
) -> tuple[int, int, str, str]:
    """Best-effort: find the line citing ``symbol`` (or the file's first line)."""
    abs_path = Path(project_root) / rel_file
    try:
        text = abs_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 1, 1, "", _hash_snippet([""])
    lines = text.splitlines() or [""]
    if symbol:
        for idx, line in enumerate(lines):
            if symbol in line:
                quote = line.strip()[:200]
                return idx + 1, idx + 1, quote, _hash_snippet([line])
    quote = lines[0].strip()[:200]
    return 1, 1, quote, _hash_snippet([lines[0]])


def _evidence_for_route(project_root: Path, route: RouteModel) -> list[Evidence]:
    ref = route.code_ref or ""
    if not ref:
        return []
    rel_file, _, symbol = ref.partition("::")
    method = ExtractionMethod.OPENAPI_VERIFIED if route.source == InputSource.OPENAPI else ExtractionMethod.AST_VERIFIED
    line_start, line_end, quote, digest = _locate_evidence(project_root, rel_file, symbol or None)
    return [
        Evidence(
            file=Path(rel_file).as_posix(),
            line_start=line_start,
            line_end=line_end,
            symbol=symbol or None,
            extraction_method=method,
            snippet_sha256=digest,
            quote=quote,
        )
    ]


def _schema_node_from_body(body: Optional[BodyModel]) -> SchemaNode:
    if body is None:
        return SchemaNode(type=FieldType.OBJECT, fields=[])
    return SchemaNode(
        type=FieldType.OBJECT,
        name=body.name,
        fields=[_schema_node_from_field(f) for f in body.fields],
    )


def _schema_node_from_field(field: BodyField) -> SchemaNode:
    return SchemaNode(
        type=field.type,
        field_name=field.name,
        required=field.required,
        description=field.description,
        items=_schema_node_from_field(field.items) if field.items else None,
        fields=[_schema_node_from_field(f) for f in field.fields],
    )


def witness_to_apim(
    witness: WitnessSet,
    *,
    project_root: Path | str = ".",
    repo_commit: Optional[str] = None,
    dirty: bool = False,
) -> ApiModel:
    """Mechanically convert a :class:`WitnessSet` into a valid, self-evidenced APIM.

    Used when no LLM-submitted model exists (legacy commands, CI, ``pipeline:
    "parser-first"``) so the *same* verify → plan → apply pipeline runs regardless of
    producer. Verification of a witness-produced model is near-trivially green since
    the witness engine is its own cross-check target.
    """
    root = Path(project_root)
    endpoints: list[Endpoint] = []
    for route in witness.routes:
        evidence = _evidence_for_route(root, route)
        uid = f"{witness.service}:{route.method.upper()}:{normalize_path(route.path)}"

        path_params = [
            Traced(value=ParamValue(name=p.name, location="path", type=p.type, required=p.required, description=p.description),
                   confidence=0.95, evidence=evidence)
            for p in route.path_params
        ]
        query_params = [
            Traced(value=ParamValue(name=p.name, location="query", type=p.type, required=p.required, description=p.description),
                   confidence=0.9, evidence=evidence)
            for p in route.query_params
        ]
        headers = [
            Traced(value=ParamValue(name=p.name, location="header", type=p.type, required=p.required, description=p.description),
                   confidence=0.9, evidence=evidence)
            for p in route.headers
        ]

        request_body = None
        if route.body is not None:
            body_conf = 0.5 if route.body.low_confidence else 0.9
            request_body = Traced(
                value=Body(schema=_schema_node_from_body(route.body)),
                confidence=body_conf,
                evidence=evidence,
            )

        responses = [
            Traced(
                value=ResponseValue(
                    status=r.status,
                    description=r.description,
                    schema=_schema_node_from_body(r.body) if r.body else None,
                ),
                confidence=0.85,
                evidence=evidence,
            )
            for r in route.responses
        ]

        auth = Traced(
            value=Auth(required=route.auth_required, scheme="bearer" if route.auth_required else "none"),
            confidence=0.9,
            evidence=evidence,
        )

        endpoints.append(
            Endpoint(
                uid=uid,
                service=witness.service,
                method=route.method.upper(),
                path=route.path,
                identity_evidence=evidence,
                description=Traced(value=route.docstring, confidence=0.6, evidence=[]) if route.docstring else None,
                path_params=path_params,
                query_params=query_params,
                headers=headers,
                request_body=request_body,
                responses=responses,
                auth=auth,
            )
        )

    return ApiModel(
        generator=GeneratorInfo(provider="witness", model=None, playbook_version="1.0"),
        repo=RepoInfo(root_hint=str(root), commit=repo_commit, dirty=dirty),
        services=[Service(id=witness.service)],
        endpoints=endpoints,
        notes=list(witness.notes),
    )
