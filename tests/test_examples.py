"""Example apps to checked-in expected-output fixtures, kept in sync.

Each ``examples/<app>/expected-output/*.item.json`` is the real parser + engine output
for that app. Regenerating here and comparing guards two things at once: the fixtures
don't silently drift, and the parser fixes (Express JSDoc body, NestJS nested-brace DTO,
Django ``.as_view`` mapping) don't regress. If the engine output legitimately changes,
regenerate the fixtures. That should be a deliberate act, not a silent one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from postman_mcp.engine.builder import build_request_item
from postman_mcp.input.parsers import parse_framework

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

# (example dir, framework): only the code-path examples with generated fixtures.
_CODE_PATH_EXAMPLES = [
    ("express-api", "express"),
    ("nestjs-api", "nestjs"),
    ("django-rest-framework", "django"),
    ("fastapi-openapi", "fastapi"),
    ("fastapi-basic", "fastapi"),
]


def _slug(method: str, path: str) -> str:
    p = re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-").lower() or "root"
    return f"{method.lower()}-{p}"


@pytest.mark.parametrize("name,framework", _CODE_PATH_EXAMPLES)
def test_example_fixtures_match_generated_output(name, framework):
    root = EXAMPLES / name
    routes, skipped = parse_framework(framework, root)
    assert skipped == [], f"{name}: parser reported skips: {skipped}"
    assert routes, f"{name}: parser found no routes"

    out_dir = root / "expected-output"
    generated = {
        _slug(r.method, r.path) + ".item.json": build_request_item(r) for r in routes
    }
    on_disk = {p.name for p in out_dir.glob("*.item.json")}
    assert on_disk == set(generated), (
        f"{name}: fixture set out of sync. on disk={sorted(on_disk)} "
        f"generated={sorted(generated)}"
    )
    for fname, item in generated.items():
        checked_in = json.loads((out_dir / fname).read_text(encoding="utf-8"))
        assert checked_in == item, f"{name}/{fname} differs from freshly generated output"
