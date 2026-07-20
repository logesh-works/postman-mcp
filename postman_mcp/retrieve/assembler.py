"""Context assembly — index → slice → budget → rendered bundle.

The bundle format is designed for the host LLM's consumption during the APIM
workflow: every chunk is headed ``## file:start-end [role]`` so citations come
pre-anchored (the LLM copies file/line spans from the headers instead of
guessing them — and the verification pipeline will hash-check whatever it
cites). Omitted chunks are listed by name so the model knows what it has NOT
seen and can request it in a follow-up ``context()`` call rather than inventing
the contents.
"""

from __future__ import annotations

from pathlib import Path

from postman_mcp.index import RepoIndex, build_index
from postman_mcp.retrieve.budget import DEFAULT_BUDGET, estimate_tokens, fit
from postman_mcp.retrieve.slicer import SliceError, slice_target

__all__ = ["assemble_context", "index_summary", "SliceError"]


def assemble_context(
    root: Path | str = ".",
    target: str = "",
    *,
    budget: int = DEFAULT_BUDGET,
    refresh: bool = False,
) -> str:
    """Return the rendered context bundle for ``target``."""
    root = Path(root)
    index = build_index(root, refresh=refresh)
    chunks = slice_target(index, root, target)
    kept, omitted = fit(chunks, budget)

    lines = [f"# Context bundle: {target}"]
    used = sum(estimate_tokens(c.text) for c in kept)
    lines.append(
        f"# chunks: {len(kept)} kept / {len(omitted)} omitted · ~{used} tokens "
        f"(budget {budget}) · index: {len(index.files)} files"
        f"{' (cached)' if index.cache_hit else ''}"
    )
    lines.append(
        "# Cite facts to the file:line spans in the chunk headers below. "
        "Content you have not seen here must not be described — request it "
        "with another context() call instead."
    )
    for chunk in kept:
        lines.append("")
        lines.append(chunk.header)
        lines.append("```")
        lines.append(chunk.text)
        lines.append("```")
    if omitted:
        lines.append("")
        lines.append("## Omitted for budget (request individually if needed):")
        for chunk in omitted:
            lines.append(f"- {chunk.file}:{chunk.line_start}-{chunk.line_end} [{chunk.role}]")
    return "\n".join(lines)


def index_summary(root: Path | str = ".", *, refresh: bool = False) -> str:
    """Build/refresh the index and render the compact repo map for the LLM."""
    root = Path(root)
    index = build_index(root, refresh=refresh)

    by_lang: dict[str, int] = {}
    for f in index.files:
        if f.language:
            by_lang[f.language] = by_lang.get(f.language, 0) + 1

    lines = [f"# Repository index — {Path(index.root).resolve().name}"]
    lines.append(
        f"files: {len(index.files)} · symbols: {len(index.symbols)} · "
        f"import edges: {len(index.imports)} · corpus witnesses: {len(index.corpus)} · "
        f"{'cache hit' if index.cache_hit else 'rebuilt'}"
    )
    lines.append("languages: " + (", ".join(f"{k}={v}" for k, v in sorted(by_lang.items())) or "none detected"))

    lines.append("")
    lines.append("## Services")
    for s in index.services:
        lines.append(f"- {s.name} · root=/{s.root} · {s.language or '?'} · {s.file_count} code files ({s.manifest or 'no manifest'})")

    decorated: dict[str, int] = {}
    for sym in index.symbols:
        if sym.decorators:
            decorated[sym.file] = decorated.get(sym.file, 0) + 1
    if decorated:
        lines.append("")
        lines.append("## Files with decorated symbols (likely handler/DTO files)")
        for file, count in sorted(decorated.items(), key=lambda kv: -kv[1])[:40]:
            lines.append(f"- {file} · {count} decorated symbols")

    kinds: dict[str, int] = {}
    for c in index.corpus:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    if kinds:
        lines.append("")
        lines.append("## Evidence corpus")
        for kind, count in sorted(kinds.items()):
            lines.append(f"- {kind}: {count}")

    lines.append("")
    lines.append(
        "Next: call context(target) per endpoint or file — e.g. "
        "context(\"app/routers/users.py\") or context(\"POST /users\") — instead of "
        "reading the repository directly."
    )
    return "\n".join(lines)
