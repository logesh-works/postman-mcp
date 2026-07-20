"""The ``cite`` tool — MCP-computed citations (``filesync.make_citations``).

The load-bearing properties: (1) round-trip — a citation this tool produces must pass
``audit_evidence`` as ``verified``, byte for byte, so no LLM ever computes a hash again;
(2) confinement — it must never read outside the project root; (3) per-item errors, never
whole-call failures.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from postman_mcp.contract.schema import Evidence
from postman_mcp.service.filesync import make_citations
from postman_mcp.verify.evidence import audit_evidence

SOURCE = textwrap.dedent("""\
    from pydantic import BaseModel


    class CreateUserDto(BaseModel):
        email: str
        password: str
    """)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "dto.py").write_text(SOURCE, encoding="utf-8")
    return tmp_path


def _call(project, spans):
    return json.loads(make_citations(spans, project_root=project))


def test_citation_round_trips_through_the_auditor(project):
    result = _call(project, [
        {"file": "src/dto.py", "line_start": 4, "line_end": 6, "symbol": "CreateUserDto"},
    ])
    [c] = result["citations"]
    assert "error" not in c
    assert c["symbol"] == "CreateUserDto"
    assert c["quote"].startswith("class CreateUserDto")
    assert len(c["snippet_sha256"]) == 64

    verdict, _ = audit_evidence(Evidence(**c), project)
    assert verdict == "verified"


def test_multiple_spans_with_per_item_errors(project):
    result = _call(project, [
        {"file": "src/dto.py", "line_start": 4, "line_end": 4},
        {"file": "src/missing.py", "line_start": 1, "line_end": 1},
        {"file": "src/dto.py", "line_start": 9, "line_end": 3},       # inverted range
        {"file": "src/dto.py", "line_start": 1, "line_end": 50},      # past EOF, within size cap
    ])
    good, missing, inverted, past_eof = result["citations"]
    assert "error" not in good
    assert "does not exist" in missing["error"]
    assert "invalid line range" in inverted["error"]
    assert "only" in past_eof["error"]


def test_paths_outside_project_root_are_refused(project):
    (project.parent / "outside.py").write_text("secret = 1\n", encoding="utf-8")
    result = _call(project, [
        {"file": "../outside.py", "line_start": 1, "line_end": 1},
        {"file": "C:/Windows/system.ini", "line_start": 1, "line_end": 1},
    ])
    for item in result["citations"]:
        assert "outside the project root" in item["error"]


def test_span_and_call_caps_enforced(project):
    too_many = [{"file": "src/dto.py", "line_start": 1, "line_end": 1}] * 201
    assert "too many spans" in json.loads(make_citations(too_many, project_root=project))["error"]

    result = _call(project, [{"file": "src/dto.py", "line_start": 1, "line_end": 500}])
    [item] = result["citations"]
    assert "span too large" in item["error"] or "only" in item["error"]
