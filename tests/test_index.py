"""Layer-0 index tests: scanner, symbols, graph, services, corpus, cache.

All tests run against a synthetic mini-repo in tmp_path — no git, no network,
no framework packages installed. The fixture uses FastAPI-*looking* code on
purpose: the index must handle it purely as Python (decorators are opaque
text), which is the framework-blindness invariant under test.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from postman_mcp.index import build_index
from postman_mcp.index.cache import cache_path
from postman_mcp.index.scanner import scan_repo


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


        @router.get("/users/{user_id}")
        def get_user(user_id: int):
            return None
        ''')
    write("app/schemas/__init__.py", "")
    write("app/schemas/user.py", f'''\
        from pydantic import BaseModel


        class Address(BaseModel):
            city: str
            zip_code: str


        class UserCreate(BaseModel):
            email: str
            address: Address


        class UserOut(BaseModel):
            """{"padding " * 600}"""

            id: int
            email: str
        ''')
    write("app/services/__init__.py", "")
    write("app/services/accounts.py", """\
        def create_account(body):
            return body
        """)
    write("app/services/billing.py", """\
        class Invoice:
            total: int


        def bill_customer():
            return None
        """)
    write("tests/test_users.py", """\
        def test_create(client):
            resp = client.post("/api/users", json={"email": "a@b.co"})
            assert resp.status_code == 201
        """)
    write("api.http", "POST {{host}}/api/users\nContent-Type: application/json\n")
    write("frontend/package.json", '{"name": "frontend", "workspaces": ["packages/*"]}\n')
    # Noise that must be ignored:
    write("node_modules/lib/index.js", "function ignored() {}\n")
    write(".venv/lib/thing.py", "def also_ignored(): ...\n")
    return tmp_path


def test_scanner_inventories_code_and_corpus_and_ignores_noise(repo: Path):
    files = scan_repo(repo)
    paths = {f.path for f in files}
    assert "app/routers/users.py" in paths
    assert "api.http" in paths
    assert "frontend/package.json" in paths
    assert not any(p.startswith(("node_modules/", ".venv/")) for p in paths)
    users = next(f for f in files if f.path == "app/routers/users.py")
    assert users.language == "python"
    assert len(users.sha256) == 64


def test_symbols_capture_decorators_bases_and_spans(repo: Path):
    index = build_index(repo)
    by_name = {s.name: s for s in index.symbols}

    create_user = by_name["create_user"]
    assert create_user.kind == "function"
    assert any("/users" in d for d in create_user.decorators)
    # line_start includes the decorator line, one above the def line
    assert create_user.line_end > create_user.line_start

    user_create = by_name["UserCreate"]
    assert user_create.kind == "class"
    assert user_create.bases == ["BaseModel"]
    assert user_create.file == "app/schemas/user.py"


def test_symbols_capture_class_fields(repo: Path):
    index = build_index(repo)
    by_name = {s.name: s for s in index.symbols}

    user_create = by_name["UserCreate"]
    assert user_create.language == "python"
    field_names = {f.name for f in user_create.fields}
    assert field_names == {"email", "address"}
    email_field = next(f for f in user_create.fields if f.name == "email")
    assert email_field.annotation == "str"

    address = by_name["Address"]
    assert {f.name for f in address.fields} == {"city", "zip_code"}

    # A plain function carries no fields at all.
    create_user = by_name["create_user"]
    assert create_user.fields == []


def test_fields_of_walks_inheritance_and_treats_basemodel_as_inert(tmp_path: Path):
    (tmp_path / "models.py").write_text(
        textwrap.dedent("""\
            from pydantic import BaseModel


            class Address(BaseModel):
                city: str
                zip_code: str


            class UserCreate(Address):
                email: str
            """),
        encoding="utf-8",
    )
    index = build_index(tmp_path)
    graph = index.graph()
    by_name = {s.name: s for s in index.symbols}

    fields, fully_resolved = graph.fields_of(by_name["UserCreate"])
    assert {f.name for f in fields} == {"email", "city", "zip_code"}
    assert fully_resolved is True  # Address resolves in-repo; BaseModel is a known-inert terminal


def test_fields_of_never_flags_non_python_symbols(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/user.dto.ts").write_text(
        "export class UserDto {\n  email: string;\n}\n", encoding="utf-8"
    )
    index = build_index(tmp_path)
    graph = index.graph()
    user_dto = next(s for s in index.symbols if s.name == "UserDto")
    assert user_dto.language != "python"

    fields, fully_resolved = graph.fields_of(user_dto)
    # No fields captured (not "confirmed empty") and never treated as fully resolved —
    # a real TS field claimed against this class must land in "unknown", never
    # "ungrounded" (see test_index_fields.py).
    assert fields == []
    assert fully_resolved is False


def test_graph_resolves_imports_and_names(repo: Path):
    index = build_index(repo)
    graph = index.graph()

    edges = {(e.src, e.dst) for e in index.imports}
    assert ("app/routers/users.py", "app/schemas/user.py") in edges
    assert ("app/routers/users.py", "app/services/accounts.py") in edges
    assert ("app/main.py", "app/routers/users.py") in edges

    sym = graph.resolve_name("UserCreate", "app/routers/users.py")
    assert sym is not None and sym.file == "app/schemas/user.py" and sym.kind == "class"

    importers = graph.importers_of("app/routers/users.py")
    assert [e.src for e in importers] == ["app/main.py"]
    assert "router" in importers[0].names


def test_services_discovered_from_manifests_not_frameworks(repo: Path):
    index = build_index(repo)
    roots = {s.root: s for s in index.services}
    assert "" in roots and roots[""].language == "python"          # pyproject.toml
    assert "frontend" in roots and roots["frontend"].language == "js"
    assert roots["frontend"].workspaces == ["packages/*"]
    assert roots[""].file_count > 0


def test_corpus_harvests_http_files_and_test_urls(repo: Path):
    index = build_index(repo)
    kinds = {(c.kind, c.method, c.path) for c in index.corpus}
    assert ("http_file", "POST", "/api/users") in kinds
    assert ("test_url", "POST", "/api/users") in kinds


def test_cache_hit_and_incremental_invalidation(repo: Path):
    first = build_index(repo)
    assert not first.cache_hit
    assert cache_path(repo).is_file()

    second = build_index(repo)
    assert second.cache_hit
    assert len(second.symbols) == len(first.symbols)

    # Change one file: only it is re-extracted; unchanged artifacts survive.
    users = repo / "app/routers/users.py"
    users.write_text(
        users.read_text(encoding="utf-8")
        + '\n\n@router.delete("/users/{user_id}")\ndef delete_user(user_id: int):\n    return None\n',
        encoding="utf-8",
    )
    third = build_index(repo)
    assert not third.cache_hit
    names = {s.name for s in third.symbols}
    assert "delete_user" in names
    assert "UserCreate" in names  # unchanged file's symbols retained

    forced = build_index(repo, refresh=True)
    assert not forced.cache_hit
    assert {s.name for s in forced.symbols} == names


def test_regex_backend_extracts_ts_classes_and_annotations(tmp_path: Path):
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src/users.controller.ts").write_text(
        textwrap.dedent("""\
            import { UserDto } from './user.dto';

            @Controller('users')
            export class UsersController {
              @Post()
              create(dto: UserDto) {
                return dto;
              }
            }
            """),
        encoding="utf-8",
    )
    (tmp_path / "src/user.dto.ts").write_text(
        "export class UserDto {\n  email: string;\n}\n", encoding="utf-8"
    )
    index = build_index(tmp_path)
    by_name = {s.name: s for s in index.symbols}
    assert by_name["UsersController"].kind == "class"
    assert any("@Controller" in d for d in by_name["UsersController"].decorators)
    assert by_name["create"].parent == "UsersController"
    assert any("@Post" in d for d in by_name["create"].decorators)
    assert ("src/users.controller.ts", "src/user.dto.ts") in {
        (e.src, e.dst) for e in index.imports
    }


def test_candidate_miner_finds_call_based_registrations(tmp_path: Path):
    """Express-style `router.get(path, handler)` is a call, not a declaration —
    symbol extraction can't see it, but the framework-blind candidate miner must."""
    (tmp_path / "routes.js").write_text(
        textwrap.dedent("""\
            const router = require('express').Router();

            function listThings(req, res) {
              res.json([]);
            }

            router.get('/things', listThings);
            router.post('/things', createThing);
            """),
        encoding="utf-8",
    )
    index = build_index(tmp_path)
    hits = {(c.method, c.path) for c in index.candidates}
    assert ("GET", "/things") in hits
    assert ("POST", "/things") in hits

    # Incremental cache: touching an unrelated file leaves mined candidates intact.
    (tmp_path / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
    second = build_index(tmp_path)
    assert not second.cache_hit
    assert {(c.method, c.path) for c in second.candidates} == hits
