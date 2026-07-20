"""Phase 5 cleanup evaluation — is it safe to remove input/parsers/, input/detect.py,
input/structural.py, or witness/engine.py yet?

The directive's rule: never remove anything unless (1) a replacement exists, (2) tests
pass, and (3) benchmark accuracy is maintained or improved. This module is the
evidence for that decision, re-derived from the real tooling (`validate_migration`,
`compare_engines`) against the same corpus `test_accuracy.py` scores the parsers
against — not an assertion, a measurement. See
``docs/architecture/phase5-cleanup-evaluation.md`` for the write-up; this file is
what that write-up's numbers come from, and it fails loudly if the underlying
tooling's behavior drifts enough to invalidate the conclusion.
"""

from __future__ import annotations

from pathlib import Path

from postman_mcp.config.store import ProjectConfig
from postman_mcp.service.compare import validate_migration
from tests.benchmark_corpus import CORPUS, HARD_CORPUS

# name -> (files, expected, framework-for-parser-dispatch). CORPUS keys already equal
# their own framework name; HARD_CORPUS carries its framework explicitly as the 3rd
# tuple element — use that rather than guessing from the scenario name.
ALL = {name: (files, expected, name) for name, (files, expected) in CORPUS.items()}
ALL.update(HARD_CORPUS)


def _materialize(root: Path, files: dict) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_graph_witness_does_not_yet_match_parser_route_recall_corpus_wide(tmp_path):
    """The quantitative Phase-1 gate from the proposal (V3 recall >= V2 recall),
    measured for real. If this ever turns green, Phase 5 removal becomes worth
    revisiting — until then, it's the hard evidence for "not yet"."""
    total_parser = 0
    total_found = 0
    failures: list[str] = []
    for name in sorted(ALL):
        root = tmp_path / name.replace("/", "_")
        root.mkdir()
        files, _expected, framework = ALL[name]
        _materialize(root, files)
        report = validate_migration(root, config=ProjectConfig(framework=framework, inputMode="code"))
        if "FAIL" in report:
            failures.append(name)
        # Pull the counts back out for an overall tally (report is human text by
        # design — MCP tools return strings — so parse the one line we need).
        line = next(l for l in report.splitlines() if l.startswith("parser routes:"))
        parser_n = int(line.split("parser routes:")[1].split("·")[0].strip())
        found_n = int(line.split("graph-found:")[1].strip())
        total_parser += parser_n
        total_found += found_n

    overall_recall = total_found / total_parser if total_parser else 1.0
    print(f"\nPhase 5 evaluation: graph-witness route recall vs parser = {overall_recall:.0%} "
          f"({total_found}/{total_parser}); scenarios failing exact-match: {failures}")

    # Documented, expected outcome today: NOT yet at parity. This assertion exists so
    # that if the gap closes (or widens further), the Phase 5 conclusion is revisited
    # against real numbers instead of going stale. (Measured 51% after fixing the
    # composition bugs this test itself uncovered — see the Phase 5 evaluation doc.)
    assert 0.40 <= overall_recall < 1.0, (
        f"expected a known, partial gap (not yet parity); got {overall_recall:.0%} — "
        "re-evaluate the Phase 5 removal decision against this number."
    )
    assert failures, "expected at least one known-hard scenario (Django ViewSet dispatch) to fail"


def test_graph_witness_extracts_no_schema_or_auth():
    """The other half of the gap validate_migration's recall number doesn't capture:
    even where routes agree, the graph witness asserts no body schema and no auth."""
    import tempfile

    from postman_mcp.verify.graph_witness import build_graph_witness

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "app.py").write_text(
            "from fastapi import FastAPI\n"
            "from pydantic import BaseModel\n\n"
            "app = FastAPI()\n\n\n"
            "class PaymentRequest(BaseModel):\n"
            "    amount: int\n\n\n"
            '@app.post("/payments")\n'
            "def create_payment(body: PaymentRequest):\n"
            "    return {}\n",
            encoding="utf-8",
        )
        ws = build_graph_witness(root)
        assert len(ws.routes) == 1
        assert ws.routes[0].body is None          # no schema extraction at all
        assert ws.routes[0].auth_required is False  # no auth claim either way — not "verified false"
