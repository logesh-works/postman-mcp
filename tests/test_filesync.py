"""The LLM-driven file sync engine — validate, verify (citations + field grounding),
diff, and the two-phase confirm write contract.

Postman REST is mocked with respx; no network. Source citations are verified against
real files written into tmp_path, mirroring tests/test_verify_pipeline.py.
"""

from __future__ import annotations

import hashlib
import json
import subprocess

import httpx
import pytest
import respx

from postman_mcp.config.store import CONFIG_FILENAME, PostmanMcpConfig
from postman_mcp.postman.client import BASE_URL
from postman_mcp.service import filesync

COLLECTION_UID = "col-123"

# Two same-named DTOs in different modules — the exact NestJS parser bug this flow fixes.
USERS_DTO = '''from pydantic import BaseModel


class CreateDto(BaseModel):
    email: str
    password: str
'''

ORDERS_DTO = '''from pydantic import BaseModel


class CreateDto(BaseModel):
    item_id: int
    quantity: int
'''


def _hash(*lines: str) -> str:
    return hashlib.sha256("\n".join(l.rstrip() for l in lines).encode("utf-8")).hexdigest()


@pytest.fixture
def project(tmp_path):
    cfg = PostmanMcpConfig()
    cfg.config.collectionId = COLLECTION_UID
    cfg.config.apiKeyRef = "file:postman/secret"
    (tmp_path / "postman").mkdir(exist_ok=True)
    (tmp_path / CONFIG_FILENAME).write_text(json.dumps(cfg.model_dump()), encoding="utf-8")
    (tmp_path / "postman/secret").write_text("PMAK-test\n", encoding="utf-8")
    (tmp_path / "users").mkdir()
    (tmp_path / "users" / "dto.py").write_text(USERS_DTO, encoding="utf-8")
    (tmp_path / "orders").mkdir()
    (tmp_path / "orders" / "dto.py").write_text(ORDERS_DTO, encoding="utf-8")
    return tmp_path


@pytest.fixture
def git_project(project):
    """A committed git repo — required for audit_evidence to distinguish a *fabricated*
    citation (provably never true) from a merely *stale* one; without git it is
    conservatively 'stale' (see verify/evidence.py)."""
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    import os
    run_env = {**os.environ, **env}
    for args in (["git", "init"], ["git", "add", "-A"], ["git", "commit", "-m", "init"]):
        subprocess.run(args, cwd=project, env=run_env, capture_output=True, check=True)
    return project


def _write_artifacts(root, collection, metadata=None, sync_config=None):
    d = root / "postman" / "sync"
    d.mkdir(parents=True, exist_ok=True)
    (d / "collection.json").write_text(json.dumps(collection), encoding="utf-8")
    if metadata is not None:
        (d / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    if sync_config is not None:
        (d / "sync.config.json").write_text(json.dumps(sync_config), encoding="utf-8")


def _write_module_artifacts(root, module, collection, metadata=None):
    d = root / "postman" / "sync" / module
    d.mkdir(parents=True, exist_ok=True)
    (d / "collection.json").write_text(json.dumps(collection), encoding="utf-8")
    if metadata is not None:
        (d / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def _request_item(name, method, path):
    return {
        "name": name,
        "request": {
            "method": method,
            "url": {"raw": "{{base_url}}" + path, "host": ["{{base_url}}"],
                    "path": [p for p in path.split("/") if p]},
        },
        "response": [],
    }


def _collection(*items):
    return {"info": {"name": "Acme", "schema": "v2.1"}, "item": list(items)}


def _module_collection(name, *items):
    """Like ``_collection`` but with a distinct ``info.name`` — module fragments each
    need their own name, unlike the single flat file ``_collection`` was built for."""
    return {"info": {"name": name, "schema": "v2.1"}, "item": list(items)}


def _dto_citation(root, module, class_name="CreateDto"):
    lines = (root / module).read_text().splitlines()
    idx = next(i for i, l in enumerate(lines) if f"class {class_name}" in l)
    return {"file": module, "line_start": idx + 1, "line_end": idx + 1, "symbol": class_name,
            "snippet_sha256": _hash(lines[idx]), "quote": lines[idx].strip()[:200]}


def _fabricated_dto_citation(module, class_name="CreateDto"):
    """A citation with a real-looking file but a hash that cannot possibly match."""
    return {"file": module, "line_start": 1, "line_end": 1, "symbol": class_name,
            "snippet_sha256": "0" * 64, "quote": "made up"}


def _mock_collection(items=None):
    return respx.get(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {"info": {"name": "Acme"}, "item": items or []}})
    )


# --- validation ---------------------------------------------------------------------


@respx.mock
def test_missing_collection_file_is_reported_no_write(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "not found" in out
    assert not put.called


@respx.mock
def test_malformed_collection_json_is_rejected_no_write(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    d = project / "postman" / "sync"
    d.mkdir(parents=True)
    (d / "collection.json").write_text("{ not valid json", encoding="utf-8")
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "not valid JSON" in out
    assert not put.called


@respx.mock
def test_collection_without_requests_is_rejected(project):
    _mock_collection()
    _write_artifacts(project, {"info": {"name": "X", "schema": "v2.1"}, "item": []})
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "no request items" in out


# --- the core win: same-named DTOs stay distinct ------------------------------------


@respx.mock
def test_two_same_named_dtos_verify_independently(project):
    _mock_collection()
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users"),
                    _request_item("Create order", "POST", "/orders")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")],
             "body": {"dto": _dto_citation(project, "users/dto.py"), "fields": ["email", "password"]}},
            {"key": "POST:/orders", "citations": [_dto_citation(project, "orders/dto.py")],
             "body": {"dto": _dto_citation(project, "orders/dto.py"), "fields": ["item_id", "quantity"]}},
        ]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "POST /users" in out and "POST /orders" in out
    assert "✓ verified" in out
    # No field warnings — each DTO's real fields were cited against its own class.
    assert "⚠" not in out


@respx.mock
def test_hallucinated_field_surfaces_warning(project):
    _mock_collection()
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")],
             "body": {"dto": _dto_citation(project, "users/dto.py"), "fields": ["email", "totallyBogus"]}},
        ]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "totallyBogus" in out and "⚠" in out


# --- citation integrity is strict; field-name accuracy is soft ----------------------


@respx.mock
def test_fabricated_dto_citation_excludes_the_endpoint(git_project):
    """A DTO citation that doesn't hash-match the code excludes the whole endpoint —
    stricter than a mere field-name mismatch, since nothing about the body claim can be
    trusted once the citation itself is fabricated."""
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        git_project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(git_project, "users/dto.py")],
             "body": {"dto": _fabricated_dto_citation("users/dto.py"), "fields": ["email"]}},
        ]},
    )
    preview = filesync.sync_from_files(project_root=git_project, confirm=False)
    assert "EXCLUDED" in preview and "request body DTO citation" in preview

    out = filesync.sync_from_files(project_root=git_project, confirm=True)
    assert "Nothing to write" in out
    assert not put.called


@respx.mock
def test_valid_dto_citation_with_bad_field_still_syncs(project):
    """The severity split is real: a correct citation with a wrong field name is a soft
    warning (already covered by test_hallucinated_field_surfaces_warning) — confirm it
    actually WRITES, unlike a fabricated citation."""
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")],
             "body": {"dto": _dto_citation(project, "users/dto.py"), "fields": ["email", "bogus"]}},
        ]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert put.called
    assert "1 added" in out


@respx.mock
def test_fabricated_auth_citation_excludes_the_endpoint(git_project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        git_project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(git_project, "users/dto.py")],
             "auth": {"cited": _fabricated_dto_citation("users/dto.py", "n/a"), "required": True}},
        ]},
    )
    preview = filesync.sync_from_files(project_root=git_project, confirm=False)
    assert "EXCLUDED" in preview and "auth citation" in preview
    out = filesync.sync_from_files(project_root=git_project, confirm=True)
    assert not put.called


@respx.mock
def test_missing_auth_claim_does_not_exclude(project):
    """No auth claim at all is informational, never punitive — the endpoint still syncs."""
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")]},
        ]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert put.called
    assert "1 added" in out


@respx.mock
def test_missing_dto_and_auth_citations_are_labeled_unverified_in_preview(project):
    """A missing DTO/auth citation is a distinct, visible state from a correctly
    verified one — not just silence — per the 'Missing Evidence (Informational)'
    severity tier."""
    _mock_collection()
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")],
             "body": {"fields": ["email"]},        # claim present, but no dto citation
             "auth": {"required": True}},          # claim present, but no citation
        ]},
    )
    preview = filesync.sync_from_files(project_root=project, confirm=False)
    assert "request body: unverified (no DTO citation)" in preview
    assert "auth: unverified (no citation)" in preview


@respx.mock
def test_verified_dto_and_auth_citations_are_labeled_verified_in_preview(project):
    _mock_collection()
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")],
             "body": {"dto": _dto_citation(project, "users/dto.py"), "fields": ["email"]},
             "auth": {"cited": _dto_citation(project, "users/dto.py"), "required": True}},
        ]},
    )
    preview = filesync.sync_from_files(project_root=project, confirm=False)
    assert "✓ request body: verified" in preview
    assert "✓ auth: verified" in preview


# --- duplicate detection -------------------------------------------------------------


@respx.mock
def test_duplicate_request_items_are_both_excluded(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        project,
        _collection(
            _request_item("Create user", "POST", "/users"),
            _request_item("Create user (dup)", "POST", "/users"),
        ),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")]}]},
    )
    preview = filesync.sync_from_files(project_root=project, confirm=False)
    assert "duplicate endpoint" in preview.lower()

    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "Nothing to write" in out
    assert not put.called


@respx.mock
def test_duplicate_metadata_entries_exclude_the_endpoint(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")]},
            {"key": "POST:/users", "citations": [_dto_citation(project, "orders/dto.py")]},
        ]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "Nothing to write" in out
    assert not put.called


@respx.mock
def test_duplicate_sibling_folder_names_block_whole_sync(project):
    """Folder integrity is a whole-file validation error, same severity as malformed
    JSON — merge.py matches folders by name, so a same-named sibling would silently
    conflate two different folders' contents."""
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    collection = {
        "info": {"name": "Acme", "schema": "v2.1"},
        "item": [
            {"name": "Users", "item": [_request_item("Create user", "POST", "/users")]},
            {"name": "Users", "item": [_request_item("List users", "GET", "/users")]},
        ],
    }
    _write_artifacts(project, collection)
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "duplicate folder name" in out
    assert not put.called


# --- per-module sync folders ---------------------------------------------------------


@respx.mock
def test_module_subfolders_become_named_folders_in_the_assembled_collection(project):
    _mock_collection()
    _write_module_artifacts(
        project, "users",
        _module_collection("Users", _request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [
            {"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")],
             "body": {"dto": _dto_citation(project, "users/dto.py"), "fields": ["email", "password"]}},
        ]},
    )
    _write_module_artifacts(
        project, "orders",
        _module_collection("Orders", _request_item("Create order", "POST", "/orders")),
        metadata={"endpoints": [
            {"key": "POST:/orders", "citations": [_dto_citation(project, "orders/dto.py")],
             "body": {"dto": _dto_citation(project, "orders/dto.py"), "fields": ["item_id", "quantity"]}},
        ]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "POST /users   → Users" in out
    assert "POST /orders   → Orders" in out
    assert "✓ verified" in out
    assert "⚠" not in out


@respx.mock
def test_module_folder_display_name_uses_collection_info_name_when_present(project):
    _mock_collection()
    _write_module_artifacts(
        project, "users",
        {"info": {"name": "User Management", "schema": "v2.1"},
         "item": [_request_item("Create user", "POST", "/users")]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "→ User Management" in out


@respx.mock
def test_root_and_module_artifacts_combine(project):
    """An ungrouped root collection.json and module subfolders can coexist — root items
    land at the collection's top level, module items each get their own named folder."""
    _mock_collection()
    _write_artifacts(project, _collection(_request_item("Health check", "GET", "/health")))
    _write_module_artifacts(
        project, "users", _module_collection("Users", _request_item("Create user", "POST", "/users")),
    )
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "GET /health   → (root)" in out
    assert "POST /users   → Users" in out


@respx.mock
def test_missing_module_metadata_is_optional(project):
    """A module with no metadata.json is allowed — its endpoints just show unverified,
    same as the flat layout's optional metadata.json."""
    _mock_collection()
    _write_module_artifacts(
        project, "users", _module_collection("Users", _request_item("Create user", "POST", "/users")),
    )
    out = filesync.sync_from_files(project_root=project, confirm=False)
    assert "unverified (no citation)" in out


@respx.mock
def test_malformed_module_collection_json_is_rejected_no_write(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    d = project / "postman" / "sync" / "users"
    d.mkdir(parents=True)
    (d / "collection.json").write_text("{ not valid json", encoding="utf-8")
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "users/collection.json is not valid JSON" in out
    assert not put.called


@respx.mock
def test_duplicate_endpoint_across_modules_is_excluded(project):
    """The same METHOD:/path defined in two different module folders is exactly as
    ambiguous as two duplicates in one file — both copies are excluded."""
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    _write_module_artifacts(project, "users", _module_collection("Users", _request_item("Create user", "POST", "/users")))
    _write_module_artifacts(project, "legacy_users", _module_collection("Legacy Users", _request_item("Create user (old)", "POST", "/users")))
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "Nothing to write" in out
    assert not put.called


# --- citation verdicts --------------------------------------------------------------


@respx.mock
def test_fabricated_citation_is_excluded_from_write(git_project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    bad = {"file": "users/dto.py", "line_start": 1, "line_end": 1,
           "snippet_sha256": "0" * 64, "quote": "made up"}
    _write_artifacts(
        git_project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [bad]}]},
    )
    preview = filesync.sync_from_files(project_root=git_project, confirm=False)
    assert "EXCLUDED" in preview or "CITATION DOES NOT MATCH" in preview

    out = filesync.sync_from_files(project_root=git_project, confirm=True)
    # The only endpoint was excluded → nothing to write, no PUT.
    assert "Nothing to write" in out
    assert not put.called


@respx.mock
def test_fabricated_citation_can_be_approved(git_project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    bad = {"file": "users/dto.py", "line_start": 1, "line_end": 1,
           "snippet_sha256": "0" * 64, "quote": "made up"}
    _write_artifacts(
        git_project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [bad]}]},
    )
    out = filesync.sync_from_files(project_root=git_project, confirm=True, approve=["POST:/users"])
    assert put.called
    assert "1 added" in out


# --- the two-phase safety contract --------------------------------------------------


@respx.mock
def test_preview_never_writes(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")]}]},
    )
    filesync.sync_from_files(project_root=project, confirm=False)
    assert not put.called


@respx.mock
def test_confirm_only_resolves_git_commit_once(git_project, monkeypatch):
    """Each `git` call is a real cost in restricted environments (AV/EDR scanning of
    child processes) — one sync_from_files(confirm=true) call must shell out to git
    exactly once (for verification), not again for the post-write marker."""
    _mock_collection()
    respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))
    _write_artifacts(
        git_project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [_dto_citation(git_project, "users/dto.py")]}]},
    )
    calls = []
    import postman_mcp.git.reader as reader
    real_current_commit = reader.current_commit

    def _spy(*args, **kwargs):
        calls.append(1)
        return real_current_commit(*args, **kwargs)

    monkeypatch.setattr(reader, "current_commit", _spy)
    filesync.sync_from_files(project_root=git_project, confirm=True)
    assert len(calls) == 1, f"expected exactly one git commit resolution, got {len(calls)}"


@respx.mock
def test_confirm_writes_once_and_preserves_human_craft(project):
    # Live collection already has this request WITH a human test script + saved example.
    live_item = _request_item("Create user", "POST", "/users")
    live_item["event"] = [{"listen": "test", "script": {"exec": ["pm.test('ok', () => {})"]}}]
    live_item["response"] = [{"name": "example", "code": 201}]
    _mock_collection(items=[live_item])
    captured = {}

    def _capture(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"collection": {}})

    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(side_effect=_capture)

    # The code now sends a header the live item doesn't have yet — a genuine structural
    # change, distinct from a no-op resync (test_confirm_resync_with_no_changes_is_a_noop
    # covers the no-op case).
    synced_item = _request_item("Create user", "POST", "/users")
    synced_item["request"]["header"] = [{"key": "Content-Type", "value": "application/json"}]
    _write_artifacts(
        project,
        _collection(synced_item),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")]}]},
    )
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert put.call_count == 1
    assert "updated" in out
    # Human-owned event + saved response survived the merge.
    written = captured["body"]["collection"]["item"][0]
    assert written.get("event")
    assert written.get("response")


@respx.mock
def test_confirm_resync_with_no_changes_is_a_noop(project):
    """The core regression this fix targets: re-syncing identical artifacts against an
    already-synced live collection must report everything UNCHANGED and skip the PUT
    entirely — not claim every endpoint was modified."""
    live_item = _request_item("Create user", "POST", "/users")
    _mock_collection(items=[live_item])
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(
        return_value=httpx.Response(200, json={"collection": {}}))

    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": [{"key": "POST:/users", "citations": [_dto_citation(project, "users/dto.py")]}]},
    )
    preview = filesync.sync_from_files(project_root=project, confirm=False)
    assert "UNCHANGED" in preview
    assert "0 modified" in preview

    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "Nothing to write" in out
    assert not put.called


# --- environment sync (createenv) ---------------------------------------------------


def _write_env(root, env):
    d = root / "postman" / "sync"
    d.mkdir(parents=True, exist_ok=True)
    (d / "environment.json").write_text(json.dumps(env), encoding="utf-8")


def _mock_no_existing_environments():
    return respx.get(f"{BASE_URL}/environments").mock(
        return_value=httpx.Response(200, json={"environments": []})
    )


@respx.mock
def test_env_preview_does_not_write(project):
    _mock_collection()
    _mock_no_existing_environments()
    post = respx.post(f"{BASE_URL}/environments").mock(return_value=httpx.Response(200, json={}))
    _write_env(project, {"name": "api env", "values": [
        {"key": "base_url", "value": "http://localhost:8000", "type": "default", "enabled": True},
        {"key": "token", "value": "", "type": "secret", "enabled": True},
    ]})
    out = filesync.sync_env_from_file(project_root=project, confirm=False)
    assert "ENV PREVIEW" in out and "base_url" in out and "secret" in out
    assert "Create this environment" in out
    assert not post.called


@respx.mock
def test_env_confirm_creates_environment(project):
    _mock_collection()
    _mock_no_existing_environments()
    post = respx.post(f"{BASE_URL}/environments").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-9"}}))
    _write_env(project, {"name": "api env", "values": [
        {"key": "base_url", "value": "http://localhost:8000", "type": "default", "enabled": True},
    ]})
    out = filesync.sync_env_from_file(project_root=project, confirm=True)
    assert post.called
    assert "env-9" in out and "Created environment" in out
    # The new environment's uid is persisted so the next run updates it instead of
    # creating a duplicate.
    from postman_mcp.config.store import load_config
    assert load_config(project).config.environmentId == "env-9"


@respx.mock
def test_env_rerun_by_configured_id_updates_not_duplicates(project):
    """Once ``environmentId`` is recorded (from a prior sync), a re-run must look it up
    by that id and update it — the concrete duplicate-on-rerun bug this fixes."""
    _mock_collection()
    respx.get(f"{BASE_URL}/environments/env-9").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-9", "name": "api env"}})
    )
    post = respx.post(f"{BASE_URL}/environments").mock(return_value=httpx.Response(200, json={}))
    put = respx.put(f"{BASE_URL}/environments/env-9").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-9"}})
    )
    _write_env(project, {"name": "api env", "values": [
        {"key": "base_url", "value": "http://localhost:9000", "type": "default", "enabled": True},
    ]})

    from postman_mcp.config.store import load_config, save_config
    cfg = load_config(project)
    cfg.config.environmentId = "env-9"
    save_config(cfg, project)

    out = filesync.sync_env_from_file(project_root=project, confirm=True)
    assert put.called
    assert not post.called
    assert "Updated environment" in out and "env-9" in out


@respx.mock
def test_env_rename_still_updates_same_environment(project):
    """The environment.json's ``name`` changing between runs (a rename) must still
    resolve to the same live environment via the stored id, not create a new one."""
    _mock_collection()
    respx.get(f"{BASE_URL}/environments/env-9").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-9", "name": "old name"}})
    )
    post = respx.post(f"{BASE_URL}/environments").mock(return_value=httpx.Response(200, json={}))
    put = respx.put(f"{BASE_URL}/environments/env-9").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-9"}})
    )
    _write_env(project, {"name": "renamed env", "values": [
        {"key": "base_url", "value": "http://localhost:8000", "type": "default", "enabled": True},
    ]})

    from postman_mcp.config.store import load_config, save_config
    cfg = load_config(project)
    cfg.config.environmentId = "env-9"
    save_config(cfg, project)

    out = filesync.sync_env_from_file(project_root=project, confirm=True)
    assert put.called and not post.called
    sent = json.loads(put.calls.last.request.content)
    assert sent["environment"]["name"] == "renamed env"


@respx.mock
def test_env_lookup_falls_back_to_name_when_configured_id_is_gone(project):
    """If the configured id 404s (deleted in Postman) but an environment with the exact
    same name still exists, update that one by name instead of creating a duplicate."""
    _mock_collection()
    respx.get(f"{BASE_URL}/environments/stale-id").mock(return_value=httpx.Response(404))
    respx.get(f"{BASE_URL}/environments").mock(
        return_value=httpx.Response(
            200, json={"environments": [{"uid": "env-live", "name": "api env"}]}
        )
    )
    post = respx.post(f"{BASE_URL}/environments").mock(return_value=httpx.Response(200, json={}))
    put = respx.put(f"{BASE_URL}/environments/env-live").mock(
        return_value=httpx.Response(200, json={"environment": {"uid": "env-live"}})
    )
    _write_env(project, {"name": "api env", "values": [
        {"key": "base_url", "value": "http://localhost:8000", "type": "default", "enabled": True},
    ]})

    from postman_mcp.config.store import load_config, save_config
    cfg = load_config(project)
    cfg.config.environmentId = "stale-id"
    save_config(cfg, project)

    out = filesync.sync_env_from_file(project_root=project, confirm=True)
    assert put.called and not post.called
    assert "env-live" in out


@respx.mock
def test_env_missing_file_is_reported(project):
    _mock_collection()
    out = filesync.sync_env_from_file(project_root=project, confirm=True)
    assert "not found" in out


@respx.mock
def test_env_invalid_shape_is_rejected_no_write(project):
    _mock_collection()
    post = respx.post(f"{BASE_URL}/environments").mock(return_value=httpx.Response(200, json={}))
    _write_env(project, {"name": "api env"})  # missing values[]
    out = filesync.sync_env_from_file(project_root=project, confirm=True)
    assert "invalid" in out and "values" in out
    assert not post.called


@respx.mock
def test_collection_mismatch_requires_confirm_collection(project):
    _mock_collection()
    put = respx.put(f"{BASE_URL}/collections/{COLLECTION_UID}").mock(return_value=httpx.Response(200, json={}))
    _write_artifacts(
        project,
        _collection(_request_item("Create user", "POST", "/users")),
        metadata={"endpoints": []},
        sync_config={"scope": "all", "collection_id": "some-other-collection"},
    )
    out = filesync.sync_from_files(project_root=project, confirm=True)
    assert "confirm_collection" in out
    assert not put.called
