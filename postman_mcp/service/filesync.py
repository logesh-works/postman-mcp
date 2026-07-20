"""The LLM-driven sync engine — read ``postman/sync/`` → validate → verify → diff → sync.

This is the deterministic MCP half of the V3 flow. The LLM authors
``postman/sync/{collection,metadata,sync.config}.json``; this module never parses source
code — it only:

1. **validates** ``collection.json`` is a well-formed Postman v2.1 collection,
2. **verifies** the LLM's claims by re-reading the exact lines cited in ``metadata.json``
   (``verify/evidence.py``) and field-grounding claimed DTO fields (``index/fields.py``),
3. **diffs** each request against the live collection (``postman/merge.py``),
4. on confirm, **merges** craft-preservingly and PUTs — the one write path.

Two-phase ``confirm`` contract, identical to ``service/sync.py::_run_sync``:
``confirm=False`` previews and writes nothing; ``confirm=True`` merges + writes.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from postman_mcp.config.store import ConfigError, save_config
from postman_mcp.contract.schema import Evidence
from postman_mcp.contract.sync_schema import Citation, EndpointMeta, SyncConfigFile, SyncMetadata
from postman_mcp.index import build_index
from postman_mcp.index.fields import ground_claimed_fields
from postman_mcp.models import normalize_path
from postman_mcp.postman import merge
from postman_mcp.postman.client import PostmanAuthError, PostmanError
from postman_mcp.service.context import SyncContext, load_context
from postman_mcp.service.sync import _record_sync
from postman_mcp.verify.evidence import audit_evidence, hash_snippet, is_confined
from postman_mcp.verify.fields import resolve_cited_class

COLLECTION_FILE = "collection.json"
METADATA_FILE = "metadata.json"
CONFIG_FILE = "sync.config.json"
ENVIRONMENT_FILE = "environment.json"


# --- loading + validation -----------------------------------------------------------


@dataclass
class SyncArtifacts:
    collection: dict[str, Any]
    metadata: SyncMetadata
    sync_config: SyncConfigFile


_ASSEMBLED_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"


def _sync_dir(root: Path, config) -> Path:
    return root / (config.config.syncDir or "postman/sync")


def _discover_modules(d: Path) -> list[Path]:
    """Immediate subdirectories of the sync dir that hold their own ``collection.json`` —
    one per module (``auth/``, ``users/``, ...). Anything else under ``d`` is ignored."""
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_dir() and (p / COLLECTION_FILE).is_file())


def _module_display_name(dirname: str, info: dict[str, Any]) -> str:
    name = (info or {}).get("name")
    if name:
        return str(name)
    return dirname.replace("_", " ").replace("-", " ").strip().title() or dirname


def _load_fragment(
    dir_path: Path, label_prefix: str, wrap_as_folder: bool,
    combined_items: list[dict[str, Any]], combined_endpoints: list[EndpointMeta], errors: list[str],
) -> None:
    """Load, validate, and fold one ``collection.json``(+``metadata.json``) pair — either
    the ungrouped root fragment or one module's — into the running composite."""
    col_path = dir_path / COLLECTION_FILE
    label = f"{label_prefix}{COLLECTION_FILE}"
    try:
        collection = json.loads(col_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return

    errs = _validate_collection(collection, label=label)
    if errs:
        errors.extend(errs)
        return

    if wrap_as_folder:
        combined_items.append({
            "name": _module_display_name(dir_path.name, collection.get("info", {})),
            "item": collection.get("item", []),
        })
    else:
        combined_items.extend(collection.get("item", []))

    meta_path = dir_path / METADATA_FILE
    if meta_path.is_file():
        try:
            metadata = SyncMetadata.model_validate_json(meta_path.read_text(encoding="utf-8"))
            combined_endpoints.extend(metadata.endpoints)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{label_prefix}{METADATA_FILE} is invalid: {exc}")


def load_artifacts(root: Path, config) -> tuple[Optional[SyncArtifacts], list[str]]:
    """Discover and assemble the sync artifacts. Returns ``(artifacts, errors)``; a
    non-empty ``errors`` list means nothing is safe to sync.

    Two kinds of source, both optional but at least one required:
    - an ungrouped ``<sync_dir>/collection.json`` (+ ``metadata.json``) — items land at
      the collection root, same as the original flat layout;
    - any number of ``<sync_dir>/<module>/collection.json`` (+ ``metadata.json``) —
      each module becomes one named folder in the assembled collection, letting the LLM
      (and ``sync <module>``) write/update one module at a time instead of regenerating
      a single monolithic file.

    ``sync.config.json``/``environment.json`` stay directly under ``<sync_dir>``,
    shared across modules.
    """
    errors: list[str] = []
    d = _sync_dir(root, config)
    module_dirs = _discover_modules(d)
    root_collection_present = (d / COLLECTION_FILE).is_file()

    if not root_collection_present and not module_dirs:
        return None, [
            f"{COLLECTION_FILE} not found under {d.as_posix()}/ — the LLM must write "
            f"{d.as_posix()}/{COLLECTION_FILE} (ungrouped) or "
            f"{d.as_posix()}/<module>/{COLLECTION_FILE} (per module) first."
        ]

    combined_items: list[dict[str, Any]] = []
    combined_endpoints: list[EndpointMeta] = []

    if root_collection_present:
        _load_fragment(d, "", wrap_as_folder=False,
                       combined_items=combined_items, combined_endpoints=combined_endpoints, errors=errors)
    for module_dir in module_dirs:
        _load_fragment(module_dir, f"{module_dir.name}/", wrap_as_folder=True,
                       combined_items=combined_items, combined_endpoints=combined_endpoints, errors=errors)

    sync_config = SyncConfigFile()
    cfg_path = d / CONFIG_FILE
    if cfg_path.is_file():
        try:
            sync_config = SyncConfigFile.model_validate_json(cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{CONFIG_FILE} is invalid: {exc}")

    if errors:
        return None, errors

    collection = {"info": {"name": "assembled", "schema": _ASSEMBLED_SCHEMA}, "item": combined_items}
    _check_folder_integrity(collection["item"], errors, label=COLLECTION_FILE)
    if errors:
        return None, errors

    return SyncArtifacts(
        collection=collection, metadata=SyncMetadata(endpoints=combined_endpoints), sync_config=sync_config,
    ), []


def _validate_collection(collection: dict[str, Any], label: str = COLLECTION_FILE) -> list[str]:
    errors: list[str] = []
    if not isinstance(collection, dict):
        return [f"{label} must be a JSON object."]
    if not isinstance(collection.get("info"), dict) or not collection["info"].get("name"):
        errors.append(f"{label}: missing info.name.")
    if not isinstance(collection.get("item"), list):
        errors.append(f"{label}: missing top-level item[] array.")
        return errors
    count = 0
    for _item, _folder, key in _walk_requests(collection):
        count += 1
        if key is None:
            errors.append(f"{label}: a request item has no resolvable method+url.")
    if count == 0:
        errors.append(f"{label}: contains no request items.")
    _check_folder_integrity(collection.get("item", []), errors, label=label)
    return errors


def _check_folder_integrity(
    items: list[dict[str, Any]], errors: list[str], trail: str = "", label: str = COLLECTION_FILE,
) -> None:
    """Sibling folders must have distinct, non-empty names — ``merge.py``'s
    ``ensure_folder``/``_find_folder`` match folders by name and would silently
    conflate two same-named siblings into one, corrupting whichever was written second."""
    names: list[str] = []
    for item in items:
        if not isinstance(item.get("item"), list):
            continue
        name = item.get("name") or ""
        where = trail or "(root)"
        if not name:
            errors.append(f"{label}: a folder under {where} has no name.")
        names.append(name)
        _check_folder_integrity(item["item"], errors, trail=f"{trail}/{name}" if trail else name, label=label)
    for name, dupe_count in Counter(n for n in names if n).items():
        if dupe_count > 1:
            errors.append(
                f"{label}: duplicate folder name {name!r} under {trail or '(root)'}."
            )


def _walk_requests(collection: dict[str, Any]):
    """Yield ``(item, folder_path, key)`` for every request, tracking its folder path."""
    def _recurse(items: list[dict[str, Any]], trail: list[str]):
        for item in items:
            if isinstance(item.get("item"), list):  # folder
                yield from _recurse(item["item"], trail + [str(item.get("name", ""))])
            elif "request" in item:
                yield item, "/".join([t for t in trail if t]), merge.item_key(item)
    yield from _recurse(collection.get("item", []), [])


# --- verification (re-read cited lines; never re-parse the repo) ---------------------


@dataclass
class EndpointVerification:
    key: str
    status: str = "unverified"          # verified | stale | fabricated | unverified
    citation_failures: list[str] = field(default_factory=list)  # body/response/auth DTO citation problems
    field_warnings: list[str] = field(default_factory=list)      # soft: field name mismatches
    notes: list[str] = field(default_factory=list)  # informational: per-dimension verified/unverified
    cite: str = ""                      # a "file:line" for the diff label

    @property
    def has_citation_failure(self) -> bool:
        return self.status == "fabricated" or bool(self.citation_failures)


def _to_evidence(c: Citation) -> Evidence:
    return Evidence(
        file=c.file, line_start=c.line_start, line_end=c.line_end, symbol=c.symbol,
        snippet_sha256=c.snippet_sha256, quote=c.quote or "",
    )


def _normalize_meta_key(key: str) -> str:
    method, _, path = key.partition(":")
    return f"{method.upper()}:{normalize_path(path or '/')}"


def _audit_citation(label: str, citation: Optional[Citation], root: Path, repo_commit: Optional[str]) -> Optional[str]:
    """Hash-verify one citation. Returns ``None`` if absent or verified; otherwise a
    human-readable failure naming *what* failed — the same rigor identity citations get,
    now applied to DTO/response/auth citations too (previously only structurally resolved,
    never hash-checked, so a fabricated DTO citation went uncaught)."""
    if citation is None:
        return None
    verdict, _ = audit_evidence(_to_evidence(citation), root, repo_commit=repo_commit)
    if verdict == "verified":
        return None
    if verdict == "stale":
        return f"{label} citation is stale ({citation.file}:{citation.line_start}) — code moved since cited"
    return f"{label} citation does not match code ({citation.file}:{citation.line_start})"


def verify_artifacts(root: Path, artifacts: SyncArtifacts, repo_commit: Optional[str]) -> dict[str, EndpointVerification]:
    """Re-verify every endpoint's citations + field claims against the working tree."""
    out: dict[str, EndpointVerification] = {}
    meta_by_key = {_normalize_meta_key(e.key): e for e in artifacts.metadata.endpoints}

    graph = None
    try:
        graph = build_index(root).graph()
    except Exception:  # pragma: no cover - index build must never block a sync
        graph = None

    for _item, _folder, key in _walk_requests(artifacts.collection):
        if key is None:
            continue
        meta = meta_by_key.get(key)
        v = EndpointVerification(key=key)
        if meta is None or not meta.citations:
            out[key] = v  # stays "unverified"
            continue

        worst = "verified"
        for c in meta.citations:
            verdict, _ = audit_evidence(_to_evidence(c), root, repo_commit=repo_commit)
            if verdict == "verified":
                if not v.cite:
                    v.cite = f"{c.file}:{c.line_start}"
                continue
            if verdict == "stale":
                worst = "stale" if worst == "verified" else worst
            else:  # fabricated / unreadable / confinement_violation
                worst = "fabricated"
        v.status = worst
        v.citation_failures, v.field_warnings, v.notes = _verify_schema_claims(graph, root, repo_commit, meta)
        out[key] = v
    return out


def _verify_schema_claims(
    graph, root: Path, repo_commit: Optional[str], meta: EndpointMeta,
) -> tuple[list[str], list[str], list[str]]:
    """Verify body/response/auth DTO claims. Returns ``(citation_failures, field_warnings,
    notes)``:

    - a **citation failure** means the DTO/auth citation itself is fabricated/stale —
      that endpoint is excluded from the write;
    - a **field warning** means the citation is fine but a claimed field wasn't found on
      the (correctly cited) class — soft, never excludes;
    - a **note** is purely informational, mirroring the identity citation's
      verified/unverified label for each dimension (body/response/auth) that has no
      citation at all to fail — "missing evidence" per the severity model, distinct from
      both a hard failure and silence.
    """
    failures: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    claims = [("request body", meta.body)] + [(f"response[{i}]", r) for i, r in enumerate(meta.responses)]
    for label, claim in claims:
        if claim is None:
            continue
        if claim.dto is None:
            notes.append(f"{label}: unverified (no DTO citation)")
            continue
        failure = _audit_citation(f"{label} DTO", claim.dto, root, repo_commit)
        if failure:
            failures.append(failure)
            continue  # don't attempt field-grounding against an unverified citation
        notes.append(f"{label}: verified ({claim.dto.file}:{claim.dto.line_start})")
        if graph is None or not claim.fields:
            continue
        cls = resolve_cited_class(graph, [_to_evidence(claim.dto)])
        if cls is None:
            continue  # hash matched, but the span isn't a recognized class — graceful no-op
        result = ground_claimed_fields(graph, cls, claim.fields)
        for missing in sorted(result.ungrounded):
            warnings.append(f"{label} field {missing!r} not found on {cls.qualname} ({cls.file})")

    if meta.auth is None:
        pass  # no auth claim at all — nothing to report; some endpoints genuinely have none
    elif meta.auth.cited is None:
        notes.append("auth: unverified (no citation)")
    else:
        failure = _audit_citation("auth", meta.auth.cited, root, repo_commit)
        if failure:
            failures.append(failure)
        else:
            notes.append(f"auth: verified ({meta.auth.cited.file}:{meta.auth.cited.line_start})")

    return failures, warnings, notes


def _find_duplicate_keys(artifacts: SyncArtifacts) -> set[str]:
    """A key appearing more than once in ``collection.json`` or ``metadata.json`` is
    ambiguous — nothing tells the MCP which copy is authoritative, so both/all copies
    are excluded rather than silently picking one (the write loop's naive ``find_item``
    against the mutating working copy would otherwise let a later duplicate silently
    overwrite an earlier one with no trace)."""
    coll_keys = [key for _item, _folder, key in _walk_requests(artifacts.collection) if key is not None]
    meta_keys = [_normalize_meta_key(e.key) for e in artifacts.metadata.endpoints]
    dupes: set[str] = set()
    for keys in (coll_keys, meta_keys):
        dupes.update(k for k, c in Counter(keys).items() if c > 1)
    return dupes


def _compute_exclusions(
    verifications: dict[str, EndpointVerification], duplicate_keys: set[str], approve_set: set[str],
) -> dict[str, str]:
    """Which endpoints are excluded from the write, and why — never a bare set, so the
    diff can always say what's wrong instead of just that something is."""
    reasons: dict[str, list[str]] = {}
    for k, v in verifications.items():
        if v.status == "fabricated":
            reasons.setdefault(k, []).append("identity citation does not match code")
        if v.citation_failures:
            reasons.setdefault(k, []).extend(v.citation_failures)
    for k in duplicate_keys:
        reasons.setdefault(k, []).append("duplicate endpoint definition")
    return {k: "; ".join(rs) for k, rs in reasons.items() if rs and k not in approve_set}


# --- diff + preview -----------------------------------------------------------------


def _render_preview(
    artifacts: SyncArtifacts,
    ctx: SyncContext,
    verifications: dict[str, EndpointVerification],
    into: Optional[str],
    excluded: dict[str, str],
) -> str:
    new = mod = unchanged = 0
    lines: list[str] = []
    for item, folder, key in _walk_requests(artifacts.collection):
        if key is None:
            continue
        existing = merge.find_item(ctx.collection, key)
        if existing is None:
            change = "NEW"
            new += 1
        elif merge.items_equivalent(existing[2], merge._merge_item(existing[2], item)):
            change = "UNCHANGED"
            unchanged += 1
        else:
            change = "MODIFY"
            mod += 1
        v = verifications.get(key, EndpointVerification(key=key))
        label = {
            "verified": f"✓ verified ({v.cite})" if v.cite else "✓ verified",
            "stale": "~ stale citation (code moved since cited)",
            "fabricated": "⚠ CITATION DOES NOT MATCH CODE",
            "unverified": "· unverified (no citation)",
        }[v.status]
        method, _, path = key.partition(":")
        loc = folder or "(root)"
        flag = f"  [EXCLUDED — {excluded[key]}]" if key in excluded else ""
        lines.append(f"[{change}] {method} {path}   → {loc}   {label}{flag}")
        if existing:
            preserved = merge._preserved_fields(existing[2])
            if preserved:
                lines.append(f"          preserves: {', '.join(preserved)}")
        for f in v.citation_failures:
            lines.append(f"          ⚠ {f}")
        for w in v.field_warnings:
            lines.append(f"          ⚠ {w}")
        for n in v.notes:
            mark = "✓" if n.split(":", 1)[1].strip().startswith("verified") else "·"
            lines.append(f"          {mark} {n}")

    header = [
        f"Collection: {ctx.collection_name or ctx.collection_id}",
        f"Plan: {new} new · {mod} modified"
        + (f" · {unchanged} unchanged" if unchanged else "")
        + (f" · {len(excluded)} excluded" if excluded else ""),
        "",
    ]
    if artifacts.sync_config.notes:
        header = ["Notes: " + "; ".join(artifacts.sync_config.notes), ""] + header
    footer = ["", "Write to Postman? Re-run with confirm=true to apply."]
    if excluded:
        footer.append(
            "Excluded endpoints failed verification (bad citation) or are duplicates — "
            "fix and re-sync, or approve explicitly via approve=[\"METHOD:/path\"]."
        )
    return "\n".join(header + lines + footer)


# --- the public entry point ---------------------------------------------------------


def sync_from_files(
    *,
    into: Optional[str] = None,
    confirm: bool = False,
    confirm_collection: bool = False,
    approve: Optional[list[str]] = None,
    project_root: Path | str = ".",
) -> str:
    """Validate → verify → diff → (confirm) merge + write the ``postman/sync/`` artifacts."""
    root = Path(project_root)
    try:
        ctx = load_context(root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    artifacts, errors = load_artifacts(root, ctx.config)
    if errors:
        ctx.client.close()
        return "Sync artifacts invalid — nothing written:\n" + "\n".join(f"  - {e}" for e in errors)

    # Optional safety: writing to a collection other than the configured one needs an
    # explicit opt-in, same spirit as the parser path's confirm_collection.
    declared = artifacts.sync_config.collection_id
    if declared and declared != ctx.collection_id and not confirm_collection:
        ctx.client.close()
        return (
            f"sync.config.json targets collection {declared!r} but postman/config.json is "
            f"configured for {ctx.collection_id!r}. Re-run with confirm_collection=true "
            "to write to a different collection."
        )

    from postman_mcp.git.reader import current_commit

    # Resolved once and threaded through both verification and the post-write marker —
    # each call shells out to `git`, a real cost in restricted environments (AV/EDR
    # scanning of child processes); one sync operation should only ever pay it once.
    repo_commit = current_commit(root)
    verifications = verify_artifacts(root, artifacts, repo_commit)
    duplicate_keys = _find_duplicate_keys(artifacts)
    approve_set = {_normalize_meta_key(k) for k in (approve or [])}
    excluded = _compute_exclusions(verifications, duplicate_keys, approve_set)

    if not confirm:
        preview = _render_preview(artifacts, ctx, verifications, into, excluded)
        ctx.client.close()
        return preview

    # --- write phase ---
    working = copy.deepcopy(ctx.collection)
    new = mod = unchanged = 0
    for item, folder, key in _walk_requests(artifacts.collection):
        if key is None or key in excluded:
            continue
        existing = merge.find_item(working, key)
        if existing is None:
            target = _folder_target(into, folder)
            folder_items = merge.ensure_folder(working, target) if target else working.setdefault("item", [])
            folder_items.append(copy.deepcopy(item))
            new += 1
        else:
            parent, idx, current = existing
            merged = merge._merge_item(current, item)
            if merge.items_equivalent(current, merged):
                # Already matches the code — leave it alone, don't count it as a write.
                unchanged += 1
                continue
            parent[idx] = merged
            mod += 1

    if new == 0 and mod == 0:
        ctx.client.close()
        return "Nothing to write — every endpoint was excluded or already up to date."

    try:
        ctx.client.update_collection(ctx.collection_id, working)
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        return f"Write aborted (no partial write): {exc}"

    _record_sync(ctx, commit=repo_commit)
    ctx.client.close()
    summary = [f"✓ {new} added · {mod} updated · written to {ctx.collection_name or ctx.collection_id}"]
    if unchanged:
        summary.append(f"✓ {unchanged} already up to date (no changes)")
    if excluded:
        summary.append(f"✓ {len(excluded)} excluded (unverifiable citation — not written)")
    summary.append("✓ lastUpdate recorded")
    return "\n".join(summary)


def _folder_target(into: Optional[str], folder: str) -> str:
    """Combine an optional ``--into`` prefix with the item's own folder path in
    collection.json — honoring the LLM's organization, prefixed if the user asked."""
    into_clean = (into or "").strip().strip("/")
    parts = [p for p in (into_clean, folder) if p]
    return "/".join(parts)


# --- citation helper (the `cite` tool) -----------------------------------------------

_MAX_CITE_SPANS = 200
_MAX_CITE_LINES = 200


def make_citations(spans: list[dict], project_root: Path | str = ".") -> str:
    """Compute complete, verification-ready citations for the given file/line spans.

    The LLM names *where* (file + line range + optional symbol); the MCP re-reads those
    exact lines and fills in ``snippet_sha256`` (via the same ``hash_snippet`` the
    auditor uses — guaranteed round-trip match) and ``quote``. This removes the one task
    no model can do natively (SHA-256), without weakening anti-hallucination: freshness
    is still enforced (the hash captures the file *now*; sync-time re-audit catches any
    drift) and span-reality is still enforced by class resolution + field grounding.

    Per-item errors, never whole-call failures. Paths are confined to the project root —
    this tool must never read outside it.
    """
    root = Path(project_root).resolve()
    if not isinstance(spans, list):
        return json.dumps({"error": "spans must be a list of {file, line_start, line_end, symbol?}"})
    if len(spans) > _MAX_CITE_SPANS:
        return json.dumps({"error": f"too many spans ({len(spans)}); max {_MAX_CITE_SPANS} per call"})

    out: list[dict] = []
    for span in spans:
        if not isinstance(span, dict):
            out.append({"error": "span must be an object"})
            continue
        file = str(span.get("file") or "")
        try:
            line_start = int(span.get("line_start", 0))
            line_end = int(span.get("line_end", line_start))
        except (TypeError, ValueError):
            out.append({"file": file, "error": "line_start/line_end must be integers"})
            continue

        if not is_confined(root, file):
            out.append({"file": file, "error": "path is outside the project root"})
            continue
        if line_start < 1 or line_end < line_start:
            out.append({"file": file, "error": f"invalid line range {line_start}-{line_end}"})
            continue
        if line_end - line_start + 1 > _MAX_CITE_LINES:
            out.append({"file": file, "error": f"span too large (>{_MAX_CITE_LINES} lines); cite tighter"})
            continue

        abs_path = root / file
        if not abs_path.is_file():
            out.append({"file": file, "error": "file does not exist"})
            continue
        lines = abs_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line_end > len(lines):
            out.append({"file": file, "error": f"file has only {len(lines)} lines; cited up to {line_end}"})
            continue

        cited = lines[line_start - 1 : line_end]
        citation = {
            "file": Path(file).as_posix(),
            "line_start": line_start,
            "line_end": line_end,
            "snippet_sha256": hash_snippet(cited),
            "quote": cited[0].strip()[:200] if cited else "",
        }
        if span.get("symbol"):
            citation["symbol"] = str(span["symbol"])
        out.append(citation)

    return json.dumps({"citations": out}, indent=2)


# --- environment sync (createenv) ---------------------------------------------------


def _validate_environment(env: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(env, dict):
        return [f"{ENVIRONMENT_FILE} must be a JSON object."]
    if not env.get("name"):
        errors.append(f"{ENVIRONMENT_FILE}: missing name.")
    values = env.get("values")
    if not isinstance(values, list):
        errors.append(f"{ENVIRONMENT_FILE}: missing values[] array.")
        return errors
    for v in values:
        if not isinstance(v, dict) or not v.get("key"):
            errors.append(f"{ENVIRONMENT_FILE}: a variable entry has no key.")
    return errors


def find_existing_environment(
    client, workspace: Optional[str], configured_id: Optional[str], name: Optional[str],
) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """Resolve the live environment a ``createenv``/``sync_env`` run should update, if
    any. Checked in order so a rename never produces a duplicate:

    1. **configured reference** — ``postman/config.json``'s ``environmentId``, the uid
       this project created/updated last time; skipped if that environment was since
       deleted.
    2. **exact name** — first environment in the workspace whose name matches exactly
       (covers the first run after upgrading, or a config that lost its reference).

    Returns ``(uid, environment)`` or ``(None, None)`` when nothing matches — the
    caller creates fresh.
    """
    if configured_id:
        found = client.get_environment(configured_id)
        if found:
            return configured_id, found
    if name:
        for candidate in client.list_environments(workspace):
            if candidate.get("name") == name:
                uid = candidate.get("uid") or candidate.get("id")
                if uid:
                    return uid, candidate
    return None, None


def sync_env_from_file(*, confirm: bool = False, project_root: Path | str = ".") -> str:
    """Preview (confirm=False) or create/update (confirm=True) the LLM-authored
    environment.

    Reads ``postman/sync/environment.json`` — the same ``{name, values:[{key,value,
    type,enabled}]}`` shape the legacy ``createenv`` produced. Looks up whether this
    project already has a managed environment (:func:`find_existing_environment`) and
    updates it in place rather than creating a duplicate; only creates a new one when
    no existing environment can be found. The LLM authors the variables
    (framework-blind); the MCP only writes them.
    """
    root = Path(project_root)
    try:
        ctx = load_context(root)
    except (ConfigError, PostmanAuthError, PostmanError) as exc:
        return f"Error: {exc}"

    env_path = _sync_dir(root, ctx.config) / ENVIRONMENT_FILE
    if not env_path.is_file():
        ctx.client.close()
        return f"{env_path.as_posix()} not found — the LLM must write it first."
    try:
        env = json.loads(env_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        ctx.client.close()
        return f"{ENVIRONMENT_FILE} is not valid JSON: {exc}"

    errors = _validate_environment(env)
    if errors:
        ctx.client.close()
        return "Environment artifact invalid — nothing written:\n" + "\n".join(f"  - {e}" for e in errors)

    values = env.get("values", [])
    existing_uid, _ = find_existing_environment(
        ctx.client, ctx.config.config.workspace, ctx.config.config.environmentId, env.get("name"),
    )

    if not confirm:
        ctx.client.close()
        lines = [f'ENV PREVIEW: "{env.get("name")}"', ""]
        for v in values:
            flag = "  (secret, masked)" if v.get("type") == "secret" else ""
            lines.append(f"  {v['key']} = {v.get('value') or '<blank>'}{flag}")
        verb = "Update" if existing_uid else "Create"
        lines += ["", f"{verb} this environment in Postman? Re-run with confirm=true to apply."]
        return "\n".join(lines)

    try:
        if existing_uid:
            result = ctx.client.update_environment(existing_uid, env)
            uid = existing_uid
        else:
            result = ctx.client.create_environment(env, ctx.config.config.workspace)
            uid = result.get("uid") or result.get("id") or "?"
    except (PostmanAuthError, PostmanError) as exc:
        ctx.client.close()
        return f"{'Update' if existing_uid else 'Create'} aborted: {exc}"

    ctx.config.config.environmentId = uid
    save_config(ctx.config, root)
    ctx.client.close()
    verb = "Updated" if existing_uid else "Created"
    return f'✓ {verb} environment "{env.get("name")}" ({uid}) with {len(values)} variables.'
