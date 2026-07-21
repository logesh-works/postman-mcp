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


def _write_many_python_files(tmp_path: Path, count: int) -> None:
    for i in range(count):
        (tmp_path / f"mod_{i:04d}.py").write_text(
            f"def handler_{i}():\n    return {i}\n", encoding="utf-8",
        )


def test_build_index_checkpoints_and_survives_a_mid_build_crash(tmp_path: Path, monkeypatch):
    """A build interrupted right after a checkpoint must not lose the files that
    checkpoint already covered — only the ones that were never actually reached."""
    import postman_mcp.index as index_mod

    monkeypatch.setattr(index_mod, "_CHECKPOINT_INTERVAL", 5)
    _write_many_python_files(tmp_path, 12)

    real_save_doc = index_mod.save_doc
    calls = {"n": 0}

    def crash_after_first_checkpoint(root, doc):
        calls["n"] += 1
        real_save_doc(root, doc)  # the checkpoint genuinely reaches disk...
        if calls["n"] == 1:
            raise RuntimeError("simulated kill right after the first checkpoint")

    monkeypatch.setattr(index_mod, "save_doc", crash_after_first_checkpoint)

    with pytest.raises(RuntimeError, match="simulated kill"):
        index_mod.build_index(tmp_path)

    # The checkpoint before the crash must have actually persisted...
    cached = index_mod.load_cached_doc(tmp_path)
    assert cached is not None
    checkpointed_paths = {f["path"] for f in cached["files"]}
    assert len(checkpointed_paths) == 5  # exactly one checkpoint's worth
    assert len(cached["symbols"]) == 5  # each checkpointed file contributed its handler

    # ...and a normal, uninterrupted retry resumes from it rather than starting over.
    monkeypatch.setattr(index_mod, "save_doc", real_save_doc)
    resumed = index_mod.build_index(tmp_path)
    assert len(resumed.files) == 12
    assert len(resumed.symbols) == 12  # one handler function per file

    # End state must be identical to a build that was never interrupted at all.
    fresh_dir = tmp_path.parent / (tmp_path.name + "_fresh")
    fresh_dir.mkdir()
    _write_many_python_files(fresh_dir, 12)
    clean = index_mod.build_index(fresh_dir)
    assert {s.name for s in clean.symbols} == {s.name for s in resumed.symbols}


def test_build_index_survives_a_pathological_file(tmp_path: Path, monkeypatch):
    """One file that blows up symbol extraction must not take the whole build down
    with it — every other file's symbols still make it into the index."""
    import postman_mcp.index as index_mod

    (tmp_path / "good.py").write_text("def fine():\n    return 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def also_fine():\n    return 2\n", encoding="utf-8")

    real_extract = index_mod.extract_symbols

    def flaky_extract(path, language, text):
        if path.endswith("bad.py"):
            raise RecursionError("simulated pathological input")
        return real_extract(path, language, text)

    monkeypatch.setattr(index_mod, "extract_symbols", flaky_extract)

    result = index_mod.build_index(tmp_path)  # must not raise
    names = {s.name for s in result.symbols}
    assert "fine" in names
    assert "also_fine" not in names  # the bad file simply contributes nothing
    assert {f.path for f in result.files} == {"good.py", "bad.py"}  # still inventoried


def test_cache_save_doc_is_atomic(tmp_path: Path, monkeypatch):
    """A write that fails partway through must never corrupt an existing cache, and
    a successful write must never leave its temp file behind."""
    from postman_mcp.index import cache as cache_mod

    cache_mod.save_doc(tmp_path, {"version": 1, "files": [], "symbols": [],
                                   "imports": [], "services": [], "corpus": [], "candidates": []})
    good_doc = cache_mod.load_cached_doc(tmp_path)
    assert good_doc is not None

    def boom(*args, **kwargs):
        raise OSError("simulated disk failure mid-write")

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(OSError):
        cache_mod.save_doc(tmp_path, {"version": 2, "files": [], "symbols": [],
                                       "imports": [], "services": [], "corpus": [], "candidates": []})

    monkeypatch.undo()
    # The original, good cache must be untouched by the failed write.
    assert cache_mod.load_cached_doc(tmp_path) == good_doc
    # And no stray .tmp files were left behind.
    leftovers = list((tmp_path / cache_mod.CACHE_DIR).glob("*.tmp"))
    assert leftovers == []


def test_cache_load_treats_corrupt_json_as_absent_not_an_error(tmp_path: Path):
    """A cache file that's present but not valid JSON — hand-edited, truncated by
    something outside our own atomic write, whatever — must fall back to `None`
    (triggering a full rebuild) rather than raising. This is the safety net the
    atomic write in save_doc() is there to make unnecessary in the common case,
    not a replacement for it."""
    from postman_mcp.index import cache as cache_mod

    path = cache_mod.cache_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    assert cache_mod.load_cached_doc(tmp_path) is None
    # And build_index() must recover cleanly (a full rebuild) rather than propagating
    # the error — a corrupt cache should never take down an otherwise-healthy sync.
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    index = build_index(tmp_path)
    assert not index.cache_hit
    assert {s.name for s in index.symbols} == {"f"}


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
