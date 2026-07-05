"""Measured route-discovery accuracy across all frameworks.

Runs each realistic app in ``benchmark_corpus`` through the real parser dispatch and
scores extracted ``METHOD:path`` against ground truth. Asserts >=90% precision and recall
per framework and overall, so "90%+ accuracy" is a number this suite enforces, not a
claim. Run ``pytest tests/test_accuracy.py -s`` to see the score table.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from postman_mcp.input.parsers import parse_framework
from tests.benchmark_corpus import CORPUS, HARD_CORPUS

THRESHOLD = 0.90

# All scored scenarios: name -> (files, expected, framework_to_parse_with)
ALL = {name: (f, e, name) for name, (f, e) in CORPUS.items()}
ALL.update(HARD_CORPUS)


def _materialize(root: Path, files: dict) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _score(scenario: str, root: Path) -> dict:
    files, expected, framework = ALL[scenario]
    _materialize(root, files)
    routes, _skipped = parse_framework(framework, root)
    extracted = {r.key for r in routes}

    matched = expected & extracted
    missing = expected - extracted          # routes we failed to find (recall miss)
    extra = extracted - expected            # routes we invented (precision miss)
    recall = len(matched) / len(expected) if expected else 1.0
    precision = len(matched) / len(extracted) if extracted else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "framework": scenario,
        "expected": len(expected),
        "extracted": len(extracted),
        "matched": len(matched),
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "missing": sorted(missing),
        "extra": sorted(extra),
    }


@pytest.mark.parametrize("framework", sorted(ALL))
def test_framework_accuracy(framework, tmp_path):
    r = _score(framework, tmp_path)
    detail = (
        f"\n{framework}: recall={r['recall']:.0%} precision={r['precision']:.0%} "
        f"f1={r['f1']:.0%} (matched {r['matched']}/{r['expected']}, "
        f"extracted {r['extracted']})"
        f"\n  missing: {r['missing']}"
        f"\n  extra:   {r['extra']}"
    )
    assert r["recall"] >= THRESHOLD, f"recall below {THRESHOLD:.0%}{detail}"
    assert r["precision"] >= THRESHOLD, f"precision below {THRESHOLD:.0%}{detail}"


def test_overall_accuracy(tmp_path, capsys):
    rows = []
    total_expected = total_matched = total_extracted = 0
    for framework in sorted(ALL):
        root = tmp_path / framework
        root.mkdir()
        r = _score(framework, root)
        rows.append(r)
        total_expected += r["expected"]
        total_matched += r["matched"]
        total_extracted += r["extracted"]

    overall_recall = total_matched / total_expected
    overall_precision = total_matched / total_extracted

    lines = ["", "=" * 64, "ROUTE-DISCOVERY ACCURACY (METHOD + full path)", "=" * 64]
    lines.append(f"{'framework':<10} {'recall':>8} {'precision':>10} {'f1':>6}  matched")
    for r in rows:
        lines.append(
            f"{r['framework']:<10} {r['recall']:>7.0%} {r['precision']:>10.0%} "
            f"{r['f1']:>5.0%}  {r['matched']}/{r['expected']}"
        )
    lines.append("-" * 64)
    lines.append(
        f"{'OVERALL':<10} {overall_recall:>7.0%} {overall_precision:>10.0%}"
        f"      {total_matched}/{total_expected}"
    )
    lines.append("=" * 64)
    with capsys.disabled():
        print("\n".join(lines))

    assert overall_recall >= THRESHOLD
    assert overall_precision >= THRESHOLD
