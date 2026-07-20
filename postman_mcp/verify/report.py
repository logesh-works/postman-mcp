"""The :class:`VerificationReport` contract — actionable by an LLM, not just a human.

Every finding names the exact check id, endpoint, and (where applicable) file/line so
a producer can re-read the cited code and resubmit a corrected model.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["block_model", "reject", "warn", "info"]
EndpointStatus = Literal["pass", "warn", "reject", "stale"]
ModelVerdict = Literal["ok", "ok_with_warnings", "endpoints_rejected", "blocked"]


class Finding(BaseModel):
    check: str  # "V-04", etc.
    severity: Severity
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class EndpointVerdict(BaseModel):
    uid: str
    verdict: EndpointStatus = "pass"
    findings: list[Finding] = Field(default_factory=list)
    confidence: dict[str, int] = Field(default_factory=dict)  # existence/path/body/auth/responses
    grades: dict[str, str] = Field(default_factory=dict)  # same keys, E1-E4 (confidence/grades.py)

    @property
    def is_rejected(self) -> bool:
        return self.verdict == "reject"

    @property
    def is_syncable(self) -> bool:
        return self.verdict in ("pass", "warn")


class WitnessSummary(BaseModel):
    agreed: int = 0
    model_only: int = 0
    witness_only: int = 0


class VerificationReport(BaseModel):
    model_id: str
    verdict: ModelVerdict = "ok"
    endpoints: dict[str, EndpointVerdict] = Field(default_factory=dict)
    witness: WitnessSummary = Field(default_factory=WitnessSummary)
    block_reason: Optional[str] = None
    summary: str = ""

    def endpoint(self, uid: str) -> Optional[EndpointVerdict]:
        return self.endpoints.get(uid)

    def syncable_uids(self) -> list[str]:
        return [uid for uid, v in self.endpoints.items() if v.is_syncable]
