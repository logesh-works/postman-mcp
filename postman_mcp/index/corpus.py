"""Evidence-corpus harvest — independent, human-authored witnesses to the API.

Collected at index time, zero tokens: OpenAPI documents, ``.http``/``.rest``
request files, URL literals in test files, existing Postman collections. The
verification layer (Phase 3) uses these to corroborate or challenge submitted
models; the retrieval layer includes matching entries in context bundles so
the host LLM sees, e.g., how a route is actually called in tests.

These witnesses matter because they are *causally independent* of the model:
they were written by people who ran the code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from postman_mcp.index.scanner import FileRecord

HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")

_HTTP_FILE_LINE = re.compile(rf"^\s*({'|'.join(HTTP_METHODS)})\s+(\S+)", re.MULTILINE)
_TEST_FILE_HINT = re.compile(r"(^|/)(tests?|__tests__|spec)(/|_)|(_test|\.test|\.spec|_spec)\.\w+$|(^|/)test_[^/]+$")
_URL_LITERAL = re.compile(r"""["'](/[A-Za-z0-9_\-{}<>:.$/]*)["']""")
_METHOD_NEARBY = re.compile(r"\b(get|post|put|patch|delete|head|options)\b", re.IGNORECASE)

MAX_ENTRIES_PER_FILE = 40


@dataclass
class CorpusEntry:
    kind: str      # "openapi" | "http_file" | "test_url" | "postman_collection"
    method: str    # may be "" when unknown
    path: str      # URL path or document path ("" for whole-document kinds)
    file: str
    line: int

    def to_doc(self) -> dict:
        return {"kind": self.kind, "method": self.method, "path": self.path,
                "file": self.file, "line": self.line}

    @classmethod
    def from_doc(cls, d: dict) -> "CorpusEntry":
        return cls(**d)


def harvest_corpus(root: Path, files: list[FileRecord]) -> list[CorpusEntry]:
    entries: list[CorpusEntry] = []
    for f in files:
        suffix = Path(f.path).suffix.lower()
        try:
            text = (root / f.path).read_text(encoding="utf-8", errors="replace")
        except OSError:  # pragma: no cover
            continue
        if suffix in (".http", ".rest"):
            entries.extend(_http_file(f.path, text))
        elif suffix in (".json", ".yaml", ".yml"):
            entries.extend(_spec_document(f.path, text, suffix))
        elif f.language and _TEST_FILE_HINT.search(f.path):
            entries.extend(_test_urls(f.path, text))
    return entries


def _http_file(path: str, text: str) -> list[CorpusEntry]:
    out = []
    for m in _HTTP_FILE_LINE.finditer(text):
        url = m.group(2)
        # strip scheme+host and {{variables}} host prefixes down to the path
        stripped = re.sub(r"^\w+://[^/]+", "", url)
        stripped = re.sub(r"^\{\{[^}]+\}\}", "", stripped)
        if stripped.startswith("/"):
            line = text[: m.start()].count("\n") + 1
            out.append(CorpusEntry("http_file", m.group(1), stripped.split("?")[0], path, line))
    return out[:MAX_ENTRIES_PER_FILE]


def _spec_document(path: str, text: str, suffix: str) -> list[CorpusEntry]:
    head = text[:2048]
    if suffix == ".json":
        if '"openapi"' in head or '"swagger"' in head:
            return _openapi_paths(path, text)
        if '"_postman_id"' in head or "schema.getpostman.com" in text[:8192]:
            return [CorpusEntry("postman_collection", "", "", path, 1)]
    else:
        if re.search(r"^\s*(openapi|swagger)\s*:", head, re.MULTILINE):
            # YAML paths mined lexically — enough for witnessing without a parse.
            out = [CorpusEntry("openapi", "", "", path, 1)]
            for m in re.finditer(r"^\s{0,4}(/[^\s:]*)\s*:", text, re.MULTILINE):
                line = text[: m.start()].count("\n") + 1
                out.append(CorpusEntry("openapi", "", m.group(1), path, line))
            return out[:MAX_ENTRIES_PER_FILE]
    return []


def _openapi_paths(path: str, text: str) -> list[CorpusEntry]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return []
    out = [CorpusEntry("openapi", "", "", path, 1)]
    for p, ops in (doc.get("paths") or {}).items():
        if isinstance(ops, dict):
            for method in ops:
                if method.upper() in HTTP_METHODS:
                    out.append(CorpusEntry("openapi", method.upper(), p, path, 1))
    return out[:MAX_ENTRIES_PER_FILE]


def _test_urls(path: str, text: str) -> list[CorpusEntry]:
    out = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        for m in _URL_LITERAL.finditer(line):
            url = m.group(1)
            if url == "/" or len(url) < 2:
                continue
            method = ""
            window = " ".join(lines[max(0, i - 2): i])
            mm = _METHOD_NEARBY.search(window)
            if mm:
                method = mm.group(1).upper()
            out.append(CorpusEntry("test_url", method, url.split("?")[0], path, i))
            if len(out) >= MAX_ENTRIES_PER_FILE:
                return out
    return out
