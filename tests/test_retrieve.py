"""Retrieval-layer tests: slicing, budgeting, bundle assembly, tool wrappers.

The bar these tests hold: for one endpoint, the bundle contains exactly the
code that matters (handler, DTO closure, called service, mount chain, test
witnesses) and NOT the rest of the repository — that is the token-scaling
property V3 exists for.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from postman_mcp.retrieve import SliceError, assemble_context, index_summary
from postman_mcp.retrieve.budget import estimate_tokens, fit
from postman_mcp.retrieve.slicer import Chunk


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    def write(rel: str, content: str) -> None:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content), encoding="utf-8")

    write("pyproject.toml", "[project]\nname = 'fixture'\n")
    write("app/__init__.py", "")
    write("app/main.py", """\
        from fastapi import FastAPI
        from app.routers.users import router

        app = FastAPI()
        app.include_router(router, prefix="/api")
        """)
    write("app/routers/__init__.py", "")
    write("app/routers/users.py", '''\
        from fastapi import APIRouter
        from app.schemas.user import UserCreate, UserOut
        from app.services.accounts import create_account

        router = APIRouter()


        @router.post("/users", response_model=UserOut)
        def create_user(body: UserCreate):
            """Create a user."""
            return create_account(body)
        ''')
    write("app/schemas/__init__.py", "")
    write("app/schemas/user.py", f'''\
        from pydantic import BaseModel


        class Address(BaseModel):
            city: str


        class UserCreate(BaseModel):
            email: str
            address: Address


        class UserOut(BaseModel):
            """{"padding " * 900}"""

            id: int
        ''')
    write("app/services/__init__.py", "")
    write("app/services/accounts.py", """\
        def create_account(body):
            return body
        """)
    write("app/services/billing.py", """\
        class Invoice:
            total: int
        """)
    write("tests/test_users.py", """\
        def test_create(client):
            resp = client.post("/api/users", json={"email": "a@b.co"})
            assert resp.status_code == 201
        """)
    write("api.http", "POST {{host}}/api/users\n")
    return tmp_path


def test_bundle_contains_slice_and_excludes_unrelated_code(repo: Path):
    bundle = assemble_context(repo, "create_user")

    assert "## app/routers/users.py:" in bundle and "[seed]" in bundle
    assert "@router.post" in bundle                       # decorators included in seed span
    assert "class UserCreate" in bundle                   # type closure hop 1
    assert "class Address" in bundle                      # nested type, hop 2
    assert "def create_account" in bundle and "[call]" in bundle
    assert "include_router" in bundle and "[mount]" in bundle
    assert "billing" not in bundle                        # unrelated file stays out
    assert "Cite facts to the file:line spans" in bundle


def test_method_path_target_finds_prefixed_route_and_witnesses(repo: Path):
    bundle = assemble_context(repo, "POST /api/users")
    # Route file declares only "/users"; "/api" prefix lives in the mount chain.
    assert "def create_user" in bundle
    assert "[witness]" in bundle
    assert "api.http" in bundle or "tests/test_users.py" in bundle


def test_budget_trims_low_rank_chunks_and_lists_omissions(repo: Path):
    bundle = assemble_context(repo, "create_user", budget=500)
    assert "def create_user" in bundle                    # seed always kept
    assert "Omitted for budget" in bundle
    assert "app/schemas/user.py" in bundle.split("Omitted for budget")[1]  # big UserOut dropped


def test_unresolvable_target_raises_readable_error(repo: Path):
    with pytest.raises(SliceError, match="no_such_symbol"):
        assemble_context(repo, "no_such_symbol")


def test_index_summary_lists_services_and_handler_files(repo: Path):
    summary = index_summary(repo)
    assert "## Services" in summary
    assert "decorated symbols" in summary
    assert "app/routers/users.py" in summary
    assert "python=" in summary


def test_fit_always_keeps_rank_zero_even_over_budget():
    big = Chunk("f.py", 1, 99, "seed", 0, "x" * 40_000)
    small = Chunk("g.py", 1, 5, "type", 1, "y" * 100)
    kept, omitted = fit([big, small], budget=500)
    assert big in kept
    assert small in omitted
    assert estimate_tokens(big.text) > 500


def test_call_based_registration_resolves_via_candidate_fallback(tmp_path: Path):
    """Express-style routes are plain calls, invisible to symbol/decorator extraction.
    context() must still resolve them via the framework-blind candidate miner."""
    (tmp_path / "routes.js").write_text(
        textwrap.dedent("""\
            const router = require('express').Router();

            function listThings(req, res) {
              res.json([]);
            }

            router.get('/things', listThings);
            """),
        encoding="utf-8",
    )
    bundle = assemble_context(tmp_path, "GET /things")
    assert "router.get('/things', listThings)" in bundle
    assert "function listThings" in bundle  # handler resolved and pulled in


def test_service_wrappers_use_cwd_and_never_raise(repo: Path, monkeypatch):
    monkeypatch.chdir(repo)
    from postman_mcp.service.repo import endpoint_context, index_repo

    assert "Repository index" in index_repo()
    assert "def create_user" in endpoint_context("create_user")
    assert "needs a target" in endpoint_context("")
    assert "Could not resolve" in endpoint_context("nonexistent_symbol_xyz")
