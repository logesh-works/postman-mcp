"""The V3 deterministic index — Layer 0 of the AI-native architecture.

Builds a framework-blind picture of the repository at zero LLM cost:

- :mod:`scanner` — file inventory (git-aware, ignore-aware, language-tagged)
- :mod:`symbols` — per-file symbol extraction (stdlib ``ast`` for Python,
  a degraded regex backend for other languages; tree-sitter slots in behind
  the same interface in a later phase)
- :mod:`graph` — import edges + name resolution across files
- :mod:`services` — manifest-based service-unit discovery (no framework detection)
- :mod:`corpus` — independent evidence harvest (OpenAPI docs, ``.http`` files,
  URL literals in tests, existing Postman collections)
- :mod:`cache` — content-addressed persistence under ``postman/index/``

Nothing in this package knows what FastAPI, Django, Express, or any other
framework is. That is a design invariant, not an accident: framework knowledge
lives only in the host LLM (see ``docs/architecture/v3-proposal.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from postman_mcp.index.cache import load_cached_doc, save_doc
from postman_mcp.index.candidates import RouteCandidate, mine_file_candidates
from postman_mcp.index.corpus import CorpusEntry, harvest_corpus
from postman_mcp.index.graph import ImportEdge, RepoGraph, extract_imports
from postman_mcp.index.scanner import FileRecord, scan_repo
from postman_mcp.index.services import ServiceUnit, discover_services
from postman_mcp.index.symbols import Symbol, extract_symbols

INDEX_VERSION = 2


@dataclass
class RepoIndex:
    """The complete Layer-0 index for one repository root."""

    root: str
    version: int = INDEX_VERSION
    files: list[FileRecord] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportEdge] = field(default_factory=list)
    services: list[ServiceUnit] = field(default_factory=list)
    corpus: list[CorpusEntry] = field(default_factory=list)
    candidates: list[RouteCandidate] = field(default_factory=list)
    cache_hit: bool = False  # true when loaded fully unchanged from disk

    def graph(self) -> RepoGraph:
        return RepoGraph(self.symbols, self.imports)

    # -- serialization ------------------------------------------------------

    def to_doc(self) -> dict:
        return {
            "version": self.version,
            "files": [f.to_doc() for f in self.files],
            "symbols": [s.to_doc() for s in self.symbols],
            "imports": [e.to_doc() for e in self.imports],
            "services": [s.to_doc() for s in self.services],
            "corpus": [c.to_doc() for c in self.corpus],
            "candidates": [c.to_doc() for c in self.candidates],
        }

    @classmethod
    def from_doc(cls, root: str, doc: dict) -> "RepoIndex":
        return cls(
            root=root,
            version=doc.get("version", 0),
            files=[FileRecord.from_doc(d) for d in doc.get("files", [])],
            symbols=[Symbol.from_doc(d) for d in doc.get("symbols", [])],
            imports=[ImportEdge.from_doc(d) for d in doc.get("imports", [])],
            services=[ServiceUnit.from_doc(d) for d in doc.get("services", [])],
            corpus=[CorpusEntry.from_doc(d) for d in doc.get("corpus", [])],
            candidates=[RouteCandidate.from_doc(d) for d in doc.get("candidates", [])],
        )


def build_index(root: Path | str = ".", *, refresh: bool = False) -> RepoIndex:
    """Build (or incrementally refresh) the index for ``root``.

    Per-file work (symbols, imports, corpus) is reused from the on-disk cache
    for every file whose content hash is unchanged; only changed/new files are
    re-extracted. ``refresh=True`` discards the cache entirely.
    """
    root = Path(root)
    files = scan_repo(root)
    by_path = {f.path: f for f in files}

    cached = None if refresh else load_cached_doc(root)
    old: dict[str, dict] = {}
    if cached and cached.get("version") == INDEX_VERSION:
        old_index = RepoIndex.from_doc(str(root), cached)
        old = {f.path: f.to_doc() for f in old_index.files}
        unchanged = {
            p for p, d in old.items()
            if p in by_path and by_path[p].sha256 == d["sha256"]
        }
        if len(unchanged) == len(files) == len(old):
            old_index.cache_hit = True
            old_index.root = str(root)
            return old_index
        # Partial reuse: keep per-file artifacts for unchanged files.
        keep_symbols = [s for s in old_index.symbols if s.file in unchanged]
        keep_imports = [e for e in old_index.imports if e.src in unchanged]
        keep_corpus = [c for c in old_index.corpus if c.file in unchanged]
        keep_candidates = [c for c in old_index.candidates if c.file in unchanged]
        todo = [f for f in files if f.path not in unchanged]
    else:
        keep_symbols, keep_imports, keep_corpus, keep_candidates = [], [], [], []
        todo = files

    services = discover_services(root, files)
    new_symbols: list[Symbol] = []
    new_imports: list[ImportEdge] = []
    new_candidates: list[RouteCandidate] = []
    for f in todo:
        text = _read(root / f.path)
        if text is None:
            continue
        new_symbols.extend(extract_symbols(f.path, f.language, text))
        new_imports.extend(extract_imports(f.path, f.language, text, by_path.keys()))
        if f.language:
            new_candidates.extend(mine_file_candidates(f.path, text))
    new_corpus = harvest_corpus(root, todo)

    index = RepoIndex(
        root=str(root),
        files=files,
        symbols=sorted(keep_symbols + new_symbols, key=lambda s: (s.file, s.line_start)),
        imports=sorted(keep_imports + new_imports, key=lambda e: (e.src, e.dst)),
        services=services,
        corpus=sorted(keep_corpus + new_corpus, key=lambda c: (c.file, c.line)),
        candidates=sorted(keep_candidates + new_candidates, key=lambda c: (c.file, c.line)),
    )
    save_doc(root, index.to_doc())
    return index


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:  # pragma: no cover - unreadable file
        return None
