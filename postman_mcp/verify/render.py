"""Render a :class:`VerificationReport` as text an LLM (or a human) can act on directly."""

from __future__ import annotations

from postman_mcp.verify.report import VerificationReport


def render_report(report: VerificationReport) -> str:
    lines = [f"model_id: {report.model_id}", f"verdict: {report.verdict}", report.summary, ""]
    for uid, ev in sorted(report.endpoints.items()):
        if ev.verdict == "pass" and not ev.findings:
            continue
        conf = " ".join(f"{k}={v}" for k, v in ev.confidence.items())
        lines.append(f"[{ev.verdict}] {uid}" + (f"  ({conf})" if conf else ""))
        for f in ev.findings:
            if f.severity == "info":
                continue
            lines.append(f"  {f.check} {f.severity}: {f.message}")
    lines.append("")
    lines.append(
        f"witness: {report.witness.agreed} agreed · {report.witness.model_only} model-only · "
        f"{report.witness.witness_only} witness-only (omitted from model)"
    )
    return "\n".join(lines)
