"""The Canonical API Model (APIM) v1 — the single contract between any LLM and MCP.

Every fact an LLM asserts about the repository is wrapped in :class:`Traced`, carrying
a confidence *suggestion* (never trusted for gating, see
``postman_mcp/confidence/scorer.py``) and a list of :class:`Evidence` citations the
verification pipeline re-reads and hashes (``postman_mcp/verify/evidence.py``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from postman_mcp.models import FieldType, normalize_path

APIM_SUPPORTED_MAJORS = (1,)
DEFAULT_APIM_VERSION = "1.0"

# Defense-in-depth document size caps — exceeding any is a BLOCK_MODEL.
MAX_ENDPOINTS = 10_000
MAX_EVIDENCE_PER_FACT = 32
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


def apim_major(version: str) -> Optional[int]:
    """Parse the major component of an ``apim_version`` string, or ``None`` if malformed."""
    try:
        return int(str(version).split(".", 1)[0])
    except (ValueError, TypeError):
        return None


class ExtractionMethod(str, Enum):
    """The evidence class — determines the confidence cap of a fact.

    Only ``AI_INFERRED`` may be asserted by an LLM submission on its own authority;
    every higher class is *earned* through MCP verification (agreement/audit), never
    submitted directly by a non-witness producer. Unknown/malformed values are
    treated as ``AI_INFERRED`` by the scorer — never as a higher class.
    """

    OPENAPI_VERIFIED = "openapi_verified"      # 100
    AST_VERIFIED = "ast_verified"              # 95
    FRAMEWORK_VERIFIED = "framework_verified"  # 90
    MULTI_SOURCE_INFERRED = "multi_source_inferred"  # 75
    AI_INFERRED = "ai_inferred"                # 50
    WEAK_INFERENCE = "weak_inference"          # 25


CLASS_CAP: dict[ExtractionMethod, int] = {
    ExtractionMethod.OPENAPI_VERIFIED: 100,
    ExtractionMethod.AST_VERIFIED: 95,
    ExtractionMethod.FRAMEWORK_VERIFIED: 90,
    ExtractionMethod.MULTI_SOURCE_INFERRED: 75,
    ExtractionMethod.AI_INFERRED: 50,
    ExtractionMethod.WEAK_INFERENCE: 25,
}

# Extraction classes a non-witness (LLM) submission may assert on its own authority.
# Anything higher is a promotion the scorer computes from audit + witness agreement.
LLM_ASSERTABLE_CLASSES = frozenset({ExtractionMethod.AI_INFERRED})


class Evidence(BaseModel):
    """One citation: a file/line/symbol span, hashed for anti-hallucination audit."""

    file: str
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    symbol: Optional[str] = None
    extraction_method: ExtractionMethod = ExtractionMethod.AI_INFERRED
    snippet_sha256: str = ""
    quote: str = Field(default="", max_length=200)


T = TypeVar("T")


class Traced(BaseModel, Generic[T]):
    """A fact wrapped with an LLM-suggested confidence and its evidence."""

    value: T
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)


class ParamValue(BaseModel):
    name: str
    location: Literal["path", "query", "header"]
    type: FieldType = FieldType.STRING
    required: bool = False
    description: Optional[str] = None


class SchemaNode(BaseModel):
    """A request/response body shape node — recursive, mirrors ``models.BodyField``."""

    type: FieldType = FieldType.OBJECT
    name: Optional[str] = None
    fields: list["SchemaNode"] = Field(default_factory=list)
    field_name: Optional[str] = None  # this node's own field name within its parent
    required: bool = True
    description: Optional[str] = None
    items: Optional["SchemaNode"] = None
    enum: list[Any] = Field(default_factory=list)
    nullable: bool = False
    example: Any = None
    ref: Optional[str] = None
    constraints: dict[str, Any] = Field(default_factory=dict)


SchemaNode.model_rebuild()


class Body(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    content_type: str = "application/json"
    schema_: SchemaNode = Field(default_factory=SchemaNode, alias="schema")
    required: bool = True


class Auth(BaseModel):
    required: bool = False
    scheme: Literal[
        "bearer", "basic", "apikey", "oauth2", "session", "custom", "none"
    ] = "none"
    detail: Optional[str] = None


class ResponseValue(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: int
    description: Optional[str] = None
    content_type: str = "application/json"
    schema_: Optional[SchemaNode] = Field(default=None, alias="schema")


class VersioningValue(BaseModel):
    scheme: Literal["path", "header", "query", "none"] = "none"
    version: Optional[str] = None


class ExamplesValue(BaseModel):
    request: Any = None
    responses: dict[str, Any] = Field(default_factory=dict)


class Service(BaseModel):
    id: str = "default"
    name: Optional[str] = None
    root_hint: str = "."


class Endpoint(BaseModel):
    uid: str
    service: str = "default"
    method: str
    path: str
    identity_evidence: list[Evidence] = Field(default_factory=list)

    operation_id: Optional[Traced[str]] = None
    summary: Optional[Traced[str]] = None
    description: Optional[Traced[str]] = None
    tags: Optional[Traced[list[str]]] = None
    folder: Optional[Traced[str]] = None
    deprecated: Traced[bool] = Field(
        default_factory=lambda: Traced[bool](value=False, confidence=1.0)
    )

    path_params: list[Traced[ParamValue]] = Field(default_factory=list)
    query_params: list[Traced[ParamValue]] = Field(default_factory=list)
    headers: list[Traced[ParamValue]] = Field(default_factory=list)

    request_body: Optional[Traced[Body]] = None
    responses: list[Traced[ResponseValue]] = Field(default_factory=list)
    auth: Traced[Auth] = Field(
        default_factory=lambda: Traced[Auth](value=Auth(), confidence=0.5)
    )
    examples: Optional[Traced[ExamplesValue]] = None
    versioning: Optional[Traced[VersioningValue]] = None

    mount_chain: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)

    def recompute_uid(self) -> str:
        """The identity MCP trusts — recomputed on ingest, never taken on faith."""
        return f"{self.service}:{self.method.upper()}:{normalize_path(self.path)}"


class FolderNode(BaseModel):
    path: str
    description: Optional[str] = None


class EnvVarSuggestion(BaseModel):
    name: str
    example_value: Optional[str] = None
    secret: bool = False


class GeneratorInfo(BaseModel):
    provider: str = "unknown"
    model: Optional[str] = None
    playbook_version: str = "1.0"


class RepoInfo(BaseModel):
    root_hint: str = "."
    commit: Optional[str] = None
    dirty: bool = False


class ApiModel(BaseModel):
    """The APIM document root."""

    apim_version: str = DEFAULT_APIM_VERSION
    generator: GeneratorInfo = Field(default_factory=GeneratorInfo)
    repo: RepoInfo = Field(default_factory=RepoInfo)
    services: list[Service] = Field(default_factory=lambda: [Service(id="default")])
    endpoints: list[Endpoint] = Field(default_factory=list)
    folders: list[FolderNode] = Field(default_factory=list)
    environments: list[EnvVarSuggestion] = Field(default_factory=list)
    components: dict[str, SchemaNode] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    def service_ids(self) -> set[str]:
        return {s.id for s in self.services}


def export_json_schema() -> dict[str, Any]:
    """The JSON Schema for :class:`ApiModel` — what ``get_contract`` publishes.

    Generated fresh from the Pydantic models on every call, so it can never drift
    from what the ingest/verification pipeline actually enforces. ``contract/schema.json``
    is a checked-in snapshot for offline/non-Python consumers; a test asserts it matches
    this output.
    """
    return ApiModel.model_json_schema()
