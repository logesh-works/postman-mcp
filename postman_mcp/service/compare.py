"""Compare tooling — V2 parser witness vs V3 graph witness (Phase 2 migration tooling).

Runs both discovery engines over the same repo and reports where they agree or
disagree, plus a migration-readiness verdict: does the graph witness find every route
the parser witness does (the quantitative Phase-1 gate from
``docs/architecture/v3-proposal.md``, rather than a leap of faith).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.config.store import ProjectConfig
from postman_mcp.verify.graph_witness import build_graph_witness
from postman_mcp.witness.engine import build_witness_set


def compare_engines(project_root: Path | str = ".", *, config: Optional[ProjectConfig] = None) -> str:
    """Diff the parser witness (V2) against the graph witness (V3) over the same repo."""
    root = Path(project_root)
    parser_ws = build_witness_set(root, config)
    graph_ws = build_graph_witness(root)

    parser_keys = set(parser_ws.by_uid)
    graph_keys = set(graph_ws.by_uid)
    agreed = sorted(parser_keys & graph_keys)
    parser_only = sorted(parser_keys - graph_keys)
    graph_only = sorted(graph_keys - parser_keys)
    recall = len(agreed) / len(parser_keys) if parser_keys else 1.0

    lines = [
        "V2 (parser) vs V3 (graph) discovery comparison",
        "",
        f"parser routes: {len(parser_keys)} · graph routes: {len(graph_keys)} · agreed: {len(agreed)}",
        f"graph recall vs parser: {recall:.0%}",
    ]
    if parser_only:
        lines.append("")
        lines.append(f"Found by parser only ({len(parser_only)}):")
        lines.extend(f"  - {uid}" for uid in parser_only)
    if graph_only:
        lines.append("")
        lines.append(f"Found by graph witness only ({len(graph_only)}):")
        lines.extend(f"  - {uid}" for uid in graph_only)
    if not parser_only and not graph_only:
        lines.append("")
        lines.append("Full agreement.")
    return "\n".join(lines)


def validate_migration(
    project_root: Path | str = ".",
    *,
    config: Optional[ProjectConfig] = None,
    min_recall: float = 1.0,
) -> str:
    """Migration-readiness gate: does the graph witness find every route the parser
    witness does? Route *recall* only — the graph witness extracts no request/response
    schema or auth, so a PASS here is never license to remove the parsers on its own
    (see the Phase 5 cleanup evaluation).
    """
    root = Path(project_root)
    parser_ws = build_witness_set(root, config)
    graph_ws = build_graph_witness(root)
    parser_keys = set(parser_ws.by_uid)
    graph_keys = set(graph_ws.by_uid)
    found = parser_keys & graph_keys
    recall = len(found) / len(parser_keys) if parser_keys else 1.0
    verdict = "PASS" if recall >= min_recall else "FAIL"
    missing = sorted(parser_keys - graph_keys)

    lines = [
        f"Migration validation: {verdict} (route recall {recall:.0%}, threshold {min_recall:.0%})",
        f"parser routes: {len(parser_keys)} · graph-found: {len(found)}",
    ]
    if missing:
        lines.append(f"Missing from graph witness ({len(missing)}):")
        lines.extend(f"  - {uid}" for uid in missing)
    lines.append("")
    lines.append(
        "Note: this validates ROUTE recall only. Request/response schema and auth "
        "detection are not produced by the graph witness (docs/architecture/"
        "v3-proposal.md, Phase 5 evaluation) — a PASS here is not license to remove "
        "the parsers on its own."
    )
    return "\n".join(lines)
