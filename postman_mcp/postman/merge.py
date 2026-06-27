"""Whole-collection merge: read → match → merge → (caller PUTs).

Identity is ``METHOD + normalized path`` matched against the *live* collection, never a
local registry. Conflict rule: **code wins on structure, human wins on craft**
— on update we overwrite structural request fields (method/url/headers/body/auth) but
read back and preserve human-owned test scripts (``event``), saved-response examples, and
edited descriptions. Deletes are soft by default.
"""

from __future__ import annotations

from typing import Any, Optional

from postman_mcp.models import (
    ChangeType,
    InputSource,
    RequestDiff,
    RouteModel,
    normalize_path,
)

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
    if existing is None:
        return RequestDiff(
            change=ChangeType.NEW,
            method=route.method.upper(),
            path=route.path,
            into=into or "/",
            source=route.source,
            lines=_new_lines(built_item, route),
            low_confidence=low_conf,
        )

    _, _, current = existing
    preserved = _preserved_fields(current)
    return RequestDiff(
        change=ChangeType.MODIFIED,
        method=route.method.upper(),
        path=route.path,
        into=into or "/",
        source=route.source,
        lines=_modified_lines(built_item, route),
        preserved=preserved,
        low_confidence=low_conf,
    )


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
    parent[idx] = merged
    return ChangeType.MODIFIED


def _merge_item(current: dict[str, Any], built: dict[str, Any]) -> dict[str, Any]:
    """Overwrite structural request fields; preserve human craft."""
    merged = dict(current)
    cur_req = dict(current.get("request") or {})
    new_req = dict(built["request"])

    # Code owns structure: method, url, header, body, auth.
    for field in ("method", "url", "header", "body", "auth"):
        if field in new_req:
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
