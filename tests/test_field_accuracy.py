"""Measured field-level accuracy: auth, params, body, responses — not just URLs.

Each dimension is scored micro-averaged across every matched route and asserted >=90%.
Run ``pytest tests/test_field_accuracy.py -s`` for the per-dimension table.
"""

from __future__ import annotations

from pathlib import Path

from postman_mcp.input.parsers import parse_framework
from tests.benchmark_fields import FIELD_CORPUS, HARD_FIELD_CORPUS, key

THRESHOLD = 0.90
SET_DIMS = ("body", "path_params", "query_params", "headers", "responses")

# scenario -> (files, expected, framework_to_parse_with)
SCENARIOS = {name: (f, e, name) for name, (f, e) in FIELD_CORPUS.items()}
SCENARIOS.update(HARD_FIELD_CORPUS)


def _materialize(root: Path, files: dict) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _actual(route) -> dict:
    return {
        "auth": bool(route.auth_required),
        "body": {f.name for f in route.body.fields} if route.body else set(),
        "path_params": {p.name for p in route.path_params},
        "query_params": {p.name for p in route.query_params},
        "headers": {h.name for h in route.headers},
        "responses": {r.status for r in route.responses},
    }


def _collect(scenario: str, root: Path):
    files, expected, framework = SCENARIOS[scenario]
    _materialize(root, files)
    routes, _ = parse_framework(framework, root)
    by_key: dict = {}
    for r in routes:
        by_key.setdefault(r.key, _actual(r))
    return expected, by_key


# accumulators across the whole corpus, per dimension
def _blank_stats():
    stats = {"auth": {"correct": 0, "total": 0}}
    for d in SET_DIMS:
        stats[d] = {"matched": 0, "expected": 0, "extracted": 0}
    return stats


def _accumulate(stats, expected, by_key):
    for k, exp in expected.items():
        act = by_key.get(k)
        if act is None:
            # route not even found — count as full miss on every dimension
            stats["auth"]["total"] += 1
            for d in SET_DIMS:
                stats[d]["expected"] += len(exp[d])
            continue
        stats["auth"]["total"] += 1
        if act["auth"] == exp["auth"]:
            stats["auth"]["correct"] += 1
        for d in SET_DIMS:
            e, a = exp[d], act[d]
            stats[d]["matched"] += len(e & a)
            stats[d]["expected"] += len(e)
            stats[d]["extracted"] += len(a)


def _rates(stats):
    out = {}
    auth = stats["auth"]
    out["auth"] = (auth["correct"] / auth["total"]) if auth["total"] else 1.0
    for d in SET_DIMS:
        s = stats[d]
        recall = s["matched"] / s["expected"] if s["expected"] else 1.0
        precision = s["matched"] / s["extracted"] if s["extracted"] else 1.0
        out[d] = min(recall, precision)
    return out


def test_field_accuracy(tmp_path, capsys):
    overall = _blank_stats()
    per_fw = {}
    for framework in sorted(SCENARIOS):
        root = tmp_path / framework
        root.mkdir()
        expected, by_key = _collect(framework, root)
        s = _blank_stats()
        _accumulate(s, expected, by_key)
        _accumulate(overall, expected, by_key)
        per_fw[framework] = _rates(s)

    dims = ("auth",) + SET_DIMS
    lines = ["", "=" * 78, "FIELD-LEVEL ACCURACY (min of precision/recall per dimension)", "=" * 78]
    header = f"{'framework':<10}" + "".join(f"{d:>11}" for d in dims)
    lines.append(header)
    lines.append("-" * 78)
    for fw in sorted(per_fw):
        row = f"{fw:<10}" + "".join(f"{per_fw[fw][d]:>10.0%} " for d in dims)
        lines.append(row)
    lines.append("-" * 78)
    o = _rates(overall)
    lines.append(f"{'OVERALL':<10}" + "".join(f"{o[d]:>10.0%} " for d in dims))
    lines.append("=" * 78)
    with capsys.disabled():
        print("\n".join(lines))

    for d in dims:
        assert o[d] >= THRESHOLD, f"dimension {d!r} below {THRESHOLD:.0%}: {o[d]:.0%}"
