"""Realistic example values from a field's type + name (PRD §8 step 3/7, §8.3).

`email` → a fake email, `amount` → a number, `created_at` → an ISO date. Deterministic
(no randomness) so re-syncs produce identical examples and the diff stays stable (§15).
"""

from __future__ import annotations

from typing import Any

from postman_mcp.models import BodyField, BodyModel, FieldType, Param

# Name-keyed heuristics (checked as substrings, first match wins) — PRD §8.3.
_NAME_HINTS: list[tuple[tuple[str, ...], Any]] = [
    (("email",), "user@example.com"),
    (("first_name", "firstname"), "Jane"),
    (("last_name", "lastname"), "Doe"),
    (("username", "user_name"), "jane_doe"),
    (("name",), "Example Name"),
    (("phone", "mobile"), "+15555550123"),
    (("password",), "S3cret!Pass"),
    (("token", "secret", "apikey", "api_key"), "{{token}}"),
    (("url", "uri", "link"), "https://example.com"),
    (("amount", "price", "total", "cost"), 4200),
    (("currency",), "USD"),
    (("count", "quantity", "qty"), 3),
    (("age",), 30),
    (("id",), 1),
    (("created_at", "updated_at", "timestamp", "date", "_at"), "2026-06-27T10:00:00Z"),
    (("status",), "active"),
    (("description", "desc", "message", "note"), "Example text"),
    (("country",), "US"),
    (("city",), "San Francisco"),
    (("zip", "postal"), "94107"),
    (("is_", "has_", "enabled", "active"), True),
]

_TYPE_DEFAULTS: dict[FieldType, Any] = {
    FieldType.STRING: "string",
    FieldType.INTEGER: 1,
    FieldType.NUMBER: 1.0,
    FieldType.BOOLEAN: True,
    FieldType.ARRAY: [],
    FieldType.OBJECT: {},
    FieldType.UNKNOWN: "value",
}


def example_for_field(field: BodyField) -> Any:
    """Produce one example value for a body field (PRD §8.3)."""
    if field.type is FieldType.OBJECT and field.fields:
        return {f.name: example_for_field(f) for f in field.fields}
    if field.type is FieldType.ARRAY:
        if field.items is not None:
            return [example_for_field(field.items)]
        return []
    return _scalar_example(field.name, field.type)


def _scalar_example(name: str, ftype: FieldType) -> Any:
    lname = name.lower()
    for needles, value in _NAME_HINTS:
        for needle in needles:
            if needle in lname:
                # Respect an explicit numeric/boolean type over a name hint string.
                if ftype in (FieldType.INTEGER, FieldType.NUMBER) and not isinstance(
                    value, (int, float)
                ):
                    break
                return value
    return _TYPE_DEFAULTS.get(ftype, "value")


def example_body(body: BodyModel) -> dict[str, Any]:
    """A full example JSON body (PRD §8 step 3/7)."""
    return {f.name: example_for_field(f) for f in body.fields}


def example_for_param(param: Param) -> str:
    """Example value for a path/query/header param (PRD §8 step 2)."""
    value = _scalar_example(param.name, param.type)
    return str(value)
