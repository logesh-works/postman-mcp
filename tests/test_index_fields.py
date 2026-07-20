"""``index/fields.py`` — classifying claimed field names against a class's own
structure (own + inherited attributes), independent of any framework knowledge.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from postman_mcp.index import build_index
from postman_mcp.index.fields import ground_claimed_fields


def _build(tmp_path: Path, source: str):
    (tmp_path / "models.py").write_text(textwrap.dedent(source), encoding="utf-8")
    index = build_index(tmp_path)
    graph = index.graph()
    by_name = {s.name: s for s in index.symbols}
    return graph, by_name


def test_ground_claimed_fields_classifies_grounded_and_ungrounded(tmp_path: Path):
    graph, by_name = _build(tmp_path, """\
        from pydantic import BaseModel


        class UserCreate(BaseModel):
            email: str
            age: int
        """)
    result = ground_claimed_fields(graph, by_name["UserCreate"], ["email", "age", "not_a_field"])
    assert result.grounded == {"email", "age"}
    assert result.ungrounded == {"not_a_field"}
    assert result.unknown == set()


def test_ground_claimed_fields_unknown_when_base_unresolvable(tmp_path: Path):
    graph, by_name = _build(tmp_path, """\
        from some_external_orm import Model


        class UserCreate(Model):
            email: str
        """)
    result = ground_claimed_fields(graph, by_name["UserCreate"], ["email", "maybe_from_orm"])
    assert result.grounded == {"email"}
    # Model isn't in-repo and isn't a known-inert base -> can't confidently say
    # `maybe_from_orm` doesn't exist; it lands in "unknown", never "ungrounded".
    assert result.unknown == {"maybe_from_orm"}
    assert result.ungrounded == set()


def test_ground_claimed_fields_inherits_from_repo_base(tmp_path: Path):
    graph, by_name = _build(tmp_path, """\
        from pydantic import BaseModel


        class Base(BaseModel):
            id: int


        class UserCreate(Base):
            email: str
        """)
    result = ground_claimed_fields(graph, by_name["UserCreate"], ["email", "id", "bogus"])
    assert result.grounded == {"email", "id"}
    assert result.ungrounded == {"bogus"}
