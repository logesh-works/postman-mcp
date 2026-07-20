"""Whole-collection merge: read → match → merge → (caller PUTs).

Identity is ``METHOD + normalized path`` matched against the *live* collection, never a
local registry. Conflict rule: **code wins on structure, human wins on craft**
— on update we overwrite structural request fields (method/url/headers/body/auth) but
read back and preserve human-owned test scripts (``event``), saved-response examples, and
edited descriptions. Deletes are soft by default.

An existing item is only ever ``NEW`` or ``MODIFIED`` at the point a route is matched —
whether it actually *changes* anything is a separate question, answered by
:func:`items_equivalent`: it simulates the merge (:func:`_merge_item`) and compares the
result to what's already live, ignoring Postman-generated identifiers and normalizing
JSON bodies/headers/response order so cosmetic differences (key order, whitespace,
an auto-assigned ``id``) never masquerade as real drift. A route whose merge would be a
complete no-op is reported/applied as ``UNCHANGED`` instead of ``MODIFIED``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from postman_mcp.models import (
    ChangeType,
    InputSource,
    RequestDiff,
    RouteModel,
    normalize_path,
)

# Fields Postman injects on its own (never present in what we build/PUT) — ignored when
# deciding whether a merge would actually change anything.
_IGNORED_KEYS = frozenset({"id", "_postman_id", "uid", "postmanId"})

_BASE_URL_PREFIX = "{{base_url}}"


# --- reading the live collection's basic structure ----------------------------------


def _item_path(item: dict[str, Any]) -> Optional[str]:
    """Extract the route path from a Postman request item's url."""
    request = item.get("request")
    if not isinstance(request, dict):
        return None
    url = request.get("url")
    raw: Optional[str] = None
    if isinstance(url, str):
        raw = url
    elif isinstance(url, dict):
        raw = url.get("raw")
        if not raw and isinstance(url.get("path"), list):
            raw = "/" + "/".join(str(p) for p in url["path"])
    if not raw:
        return None
    raw = raw.replace(_BASE_URL_PREFIX, "")
    # strip protocol/host if a literal URL slipped in
    if "://" in raw:
        raw = "/" + raw.split("://", 1)[1].split("/", 1)[-1]
    raw = raw.split("?", 1)[0]
    return raw or "/"


def item_key(item: dict[str, Any]) -> Optional[str]:
    """``METHOD:/normalized`` key for a request item, or None if not a request."""
    request = item.get("request")
    if not isinstance(request, dict):
        return None
    method = request.get("method")
    path = _item_path(item)
    if not method or path is None:
        return None
    return f"{method.upper()}:{normalize_path(path)}"


def _iter_request_items(items: list[dict[str, Any]]):
    """Yield ``(parent_list, index, item)`` for every request item, recursing folders."""
    for idx, item in enumerate(items):
        if isinstance(item.get("item"), list):  # folder
            yield from _iter_request_items(item["item"])
        elif "request" in item:
            yield items, idx, item


def find_item(
    collection: dict[str, Any], key: str
) -> Optional[tuple[list[dict[str, Any]], int, dict[str, Any]]]:
    """Find a request item by its METHOD+path key anywhere in the collection."""
    items = collection.get("item", [])
    for parent, idx, item in _iter_request_items(items):
        if item_key(item) == key:
            return parent, idx, item
    return None


def ensure_folder(collection: dict[str, Any], into: str) -> list[dict[str, Any]]:
    """Resolve/create the ``--into`` folder path; return its item list."""
    items = collection.setdefault("item", [])
    into = (into or "/").strip("/")
    if not into:
        return items
    current = items
    for segment in into.split("/"):
        folder = _find_folder(current, segment)
        if folder is None:
            folder = {"name": segment, "item": []}
            current.append(folder)
        current = folder.setdefault("item", [])
    return current


def _find_folder(items: list[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
    for item in items:
        if item.get("name") == name and isinstance(item.get("item"), list):
            return item
    return None


# --- diff computation (no mutation) -------------------------------------------------


def compute_diff(
    collection: dict[str, Any],
    built_item: dict[str, Any],
    route: RouteModel,
    into: str,
) -> RequestDiff:
    """Compute the planned change for one route without mutating."""
    existing = find_item(collection, route.key)
    low_conf = bool(route.body and route.body.low_confidence)
    table_cells = dict(
        auth=_auth_cell(route),
        body_name=_body_cell(route),
        response_name=_response_cell(route),
    )
    if existing is None:
        return RequestDiff(
            change=ChangeType.NEW,
            method=route.method.upper(),
            path=route.path,
            into=into or "/",
            source=route.source,
            lines=_new_lines(built_item, route),
            low_confidence=low_conf,
            **table_cells,
        )

    _, _, current = existing
    preserved = _preserved_fields(current)
    merged_preview = _merge_item(current, built_item)
    if items_equivalent(current, merged_preview):
        return RequestDiff(
            change=ChangeType.UNCHANGED,
            method=route.method.upper(),
            path=route.path,
            into=into or "/",
            source=route.source,
            lines=[],
            preserved=preserved,
            low_confidence=low_conf,
            **table_cells,
        )
    return RequestDiff(
        change=ChangeType.MODIFIED,
        method=route.method.upper(),
        path=route.path,
        into=into or "/",
        source=route.source,
        lines=_modified_lines(built_item, route),
        preserved=preserved,
        low_confidence=low_conf,
        **table_cells,
    )


def _auth_cell(route: RouteModel) -> str:
    return "Bearer" if route.auth_required else "—"


def _body_cell(route: RouteModel) -> str:
    if route.body is None:
        return "N/A"
    return route.body.name or "Body"


def _response_cell(route: RouteModel) -> str:
    declared_2xx = [r for r in route.responses if 200 <= r.status < 300]
    if not declared_2xx:
        return "—"
    resp = declared_2xx[0]
    if resp.body and resp.body.name:
        return resp.body.name
    return f"{resp.status} {resp.description or ''}".strip()


def _preserved_fields(current: dict[str, Any]) -> list[str]:
    """List human-owned fields that will survive the update."""
    preserved: list[str] = []
    if current.get("event"):
        preserved.append("test scripts")
    if current.get("response"):
        preserved.append("saved examples / responses")
    if (current.get("request") or {}).get("description"):
        preserved.append("edited description")
    return preserved


def _new_lines(built_item: dict[str, Any], route: RouteModel) -> list[str]:
    req = built_item["request"]
    lines = [f"+ Request    {req['method']} {req['url']['raw']}"]
    if route.auth_required:
        lines.append("+ Auth       Bearer {{token}}")
    if "body" in req:
        raw = req["body"].get("raw", "")
        compact = " ".join(raw.split())
        lines.append(f"+ Body       {compact[:80]}")
    codes = sorted({r["code"] for r in built_item.get("response", [])})
    if codes:
        lines.append("+ Responses  " + ", ".join(str(c) for c in codes))
    if built_item.get("event"):
        lines.append("+ Tests      status · schema")
    ex = len(built_item.get("response", []))
    lines.append(f"+ Examples   {ex} saved")
    return lines


def _modified_lines(built_item: dict[str, Any], route: RouteModel) -> list[str]:
    req = built_item["request"]
    lines = [f"~ Request    {req['method']} {req['url']['raw']}"]
    if "body" in req:
        lines.append("~ Body       (structural fields updated from code)")
    codes = sorted({r["code"] for r in built_item.get("response", [])})
    if codes:
        lines.append("~ Responses  " + ", ".join(str(c) for c in codes))
    return lines


# --- applying the change (mutation; only on confirm) --------------------------------


def apply_route(
    collection: dict[str, Any],
    built_item: dict[str, Any],
    route: RouteModel,
    into: str,
) -> ChangeType:
    """Merge one route into the collection in place; return what happened."""
    existing = find_item(collection, route.key)
    if existing is None:
        folder_items = ensure_folder(collection, into)
        folder_items.append(built_item)
        return ChangeType.NEW

    parent, idx, current = existing
    merged = _merge_item(current, built_item)
    if items_equivalent(current, merged):
        return ChangeType.UNCHANGED
    parent[idx] = merged
    return ChangeType.MODIFIED


# --- equivalence (is a merge actually a no-op?) --------------------------------------


def items_equivalent(current: dict[str, Any], merged: dict[str, Any]) -> bool:
    """True when applying ``merged`` over ``current`` would change nothing observable.

    Compares the two Postman items after :func:`_normalize` strips Postman-generated
    identifiers and canonicalizes JSON bodies/headers/response ordering — so a request
    that already matches the code (same method/url/headers/body/auth; unmodified
    human-owned event/response/description, which ``_merge_item`` never touches when
    already present) reports ``UNCHANGED`` instead of ``MODIFIED``.
    """
    return _normalize(current) == _normalize(merged)


# List/string fields where "absent" and "explicitly empty" are the same thing in
# Postman's schema (e.g. no test scripts vs. ``event: []``) — normalized away so an
# item built fresh (which always states these keys, even empty) never looks different
# from a live item that simply omits them.
_DROP_IF_EMPTY_LIST = frozenset({"event", "response", "header", "query", "variable"})
_DROP_IF_EMPTY_STRING = frozenset({"description"})


def _normalize(value: Any, key: Optional[str] = None) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in _IGNORED_KEYS:
                continue
            nv = _normalize(v, key=k)
            if k in _DROP_IF_EMPTY_LIST and nv == []:
                continue
            if k in _DROP_IF_EMPTY_STRING and nv == "":
                continue
            out[k] = nv
        return out
    if isinstance(value, list):
        if key == "header":
            return _normalize_headers(value)
        if key == "response":
            return _normalize_responses(value)
        return [_normalize(v) for v in value]
    if isinstance(value, str) and key in ("body", "raw"):
        parsed = _try_json(value)
        return parsed if parsed is not None else value.strip()
    return value


def _normalize_headers(headers: list[Any]) -> list[tuple[tuple[str, Any], ...]]:
    """Order-insensitive, but keeps every field (``key``/``value``/``disabled``/...) —
    not just key+value — so e.g. a header flipping required↔disabled still counts as a
    real change instead of being silently discarded."""
    normed = [
        tuple(sorted(_normalize(h).items())) for h in headers if isinstance(h, dict)
    ]
    return sorted(normed)


def _normalize_responses(responses: list[Any]) -> list[dict[str, Any]]:
    normed = [_normalize(r) for r in responses if isinstance(r, dict)]
    normed.sort(key=lambda r: (r.get("code") or 0, str(r.get("name") or "")))
    return normed


def _try_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _merge_url(current_url: Optional[dict[str, Any]], new_url: dict[str, Any]) -> dict[str, Any]:
    """Code owns ``raw``/``host``/``path``/``query`` — but ``variable`` is special:
    Postman auto-derives it (``{"key": "id"}`` per ``:id``/``{id}`` path token) the
    moment a collection with a templated path round-trips through its API, whether or
    not the request we PUT included one. The documented request-builder shape never
    authors a ``variable`` array at all (path params stay literal in ``path``), so
    without this, every ``:param`` route would permanently look "modified" (Postman's
    own auto-added array vs. our url that never has one) and, worse, a real write would
    silently discard any variable description/example a human had set in Postman.
    Keep the live ``variable`` when the code-built url doesn't specify one.
    """
    merged_url = dict(new_url)
    if "variable" not in merged_url:
        live_variable = (current_url or {}).get("variable")
        if isinstance(live_variable, list) and live_variable:
            merged_url["variable"] = live_variable
    return merged_url


def _merge_item(current: dict[str, Any], built: dict[str, Any]) -> dict[str, Any]:
    """Overwrite structural request fields; preserve human craft."""
    merged = dict(current)
    cur_req = dict(current.get("request") or {})
    new_req = dict(built["request"])

    # Code owns structure: method, url, header, body, auth.
    for field in ("method", "url", "header", "body", "auth"):
        if field == "url" and field in new_req:
            cur_req[field] = _merge_url(cur_req.get("url"), new_req["url"])
        elif field in new_req:
            cur_req[field] = new_req[field]
        elif field in cur_req and field in ("body", "auth"):
            # route no longer has a body/auth → drop the stale structural field
            cur_req.pop(field, None)

    # Human owns the description if they edited one; else take the code docstring.
    if not cur_req.get("description"):
        cur_req["description"] = new_req.get("description", "")

    merged["request"] = cur_req
    # Preserve human-owned scripts + saved examples; add only if absent.
    if not merged.get("event"):
        merged["event"] = built.get("event", [])
    if not merged.get("response"):
        merged["response"] = built.get("response", [])
    merged["name"] = current.get("name") or built.get("name")
    return merged


# --- soft delete -----------------------------------------------------

_DEPRECATED_PREFIX = "[DEPRECATED] "


def soft_deprecate(collection: dict[str, Any], key: str) -> bool:
    """Mark a removed route deprecated without deleting it."""
    found = find_item(collection, key)
    if found is None:
        return False
    _, _, item = found
    name = item.get("name", "")
    if not name.startswith(_DEPRECATED_PREFIX):
        item["name"] = _DEPRECATED_PREFIX + name
    req = item.setdefault("request", {})
    desc = req.get("description", "") or ""
    note = "Route removed from code — soft-deprecated by postman-mcp."
    if note not in desc:
        req["description"] = (desc + "\n\n" + note).strip()
    return True


def purge(collection: dict[str, Any], key: str) -> bool:
    """Hard-delete a request item (only when ``--purge`` is given)."""
    found = find_item(collection, key)
    if found is None:
        return False
    parent, idx, _ = found
    parent.pop(idx)
    return True
