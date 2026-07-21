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
lives only in the host LLM (see ``docs/architecture/indexing.md``).
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

# How many files to extract between cache checkpoints during a build. A large,
# previously-unindexed repository can take long enough that a build gets killed or
# a client stops waiting partway through; checkpointing bounds how much of that work
# is ever lost, instead of the all-or-nothing single save at the end. Small enough
# that a kill loses at most a few seconds of re-work, large enough that the
# serialize-and-write itself isn't a meaningful fraction of total build time.
_CHECKPOINT_INTERVAL = 200


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

    Extraction is checkpointed to disk every :data:`_CHECKPOINT_INTERVAL` files
    (see :func:`postman_mcp.index.cache.save_doc` for the atomic-write guarantee
    that makes this safe). On a large, previously-unindexed repository this is
    the difference between "an interrupted run loses a few seconds of work" and
    "an interrupted run loses everything and the next attempt starts from zero" —
    the latter turns a slow first index into one that never actually finishes if
    something keeps cutting it off partway through (a client-side timeout, a
    cancelled tool call, a killed process).
    """
    root = Path(root)
    files = scan_repo(root)
    by_path = {f.path: f for f in files}

    cached = None if refresh else load_cached_doc(root)
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
        # Partial reuse: keep per-file artifacts for unchanged files. This is also
        # how a checkpointed-but-interrupted build resumes: files already committed
        # to disk by a prior checkpoint show up here as "unchanged" and are skipped,
        # so only what was never actually finished ends up back in `todo`.
        keep_files = [f for f in old_index.files if f.path in unchanged]
        keep_symbols = [s for s in old_index.symbols if s.file in unchanged]
        keep_imports = [e for e in old_index.imports if e.src in unchanged]
        keep_corpus = [c for c in old_index.corpus if c.file in unchanged]
        keep_candidates = [c for c in old_index.candidates if c.file in unchanged]
        todo = [f for f in files if f.path not in unchanged]
    else:
        keep_files = []
        keep_symbols, keep_imports, keep_corpus, keep_candidates = [], [], [], []
        todo = files

    services = discover_services(root, files)
    done_files: list[FileRecord] = list(keep_files)
    new_symbols: list[Symbol] = []
    new_imports: list[ImportEdge] = []
    new_candidates: list[RouteCandidate] = []
    new_corpus: list[CorpusEntry] = []

    def checkpoint(file_list: list[FileRecord]) -> None:
        """Persist everything extracted so far. `files` here is deliberately just
        the subset actually done — never the full scan — so a resumed build's
        `unchanged` check above only ever credits work that really happened."""
        partial = RepoIndex(
            root=str(root),
            files=file_list,
            symbols=sorted(keep_symbols + new_symbols, key=lambda s: (s.file, s.line_start)),
            imports=sorted(keep_imports + new_imports, key=lambda e: (e.src, e.dst)),
            services=services,
            corpus=sorted(keep_corpus + new_corpus, key=lambda c: (c.file, c.line)),
            candidates=sorted(keep_candidates + new_candidates, key=lambda c: (c.file, c.line)),
        )
        save_doc(root, partial.to_doc())

    for i, f in enumerate(todo, start=1):
        text = _read(root / f.path)
        if text is not None:
            try:
                new_symbols.extend(extract_symbols(f.path, f.language, text))
                new_imports.extend(extract_imports(f.path, f.language, text, by_path.keys()))
                if f.language:
                    new_candidates.extend(mine_file_candidates(f.path, text))
                new_corpus.extend(harvest_corpus(root, [f]))
            except Exception:
                # One pathological file (deeply nested/generated/minified content
                # tripping the regex backend or ast's recursion limit) must not
                # abort the whole build and forfeit everything already checkpointed.
                # It's simply treated as contributing no symbols — same outcome as
                # an unparseable file, which the Python backend already tolerates
                # via its own SyntaxError guard.
                pass
        done_files.append(f)
        if i % _CHECKPOINT_INTERVAL == 0:
            checkpoint(done_files)

    index = RepoIndex(
        root=str(root),
        files=files,  # the full scan, now that every file in it has actually been processed
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
