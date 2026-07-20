"""Framework-blind route-candidate mining — a Layer-0 primitive.

Flags any line whose shape is "an HTTP-verb-like call/annotation next to a
path-like string literal": ``@app.get("/x")``, ``router.post('/y')``,
``@GetMapping("/z")``, ``app.use(routes)`` style generic-route calls, and so
on. This is deliberately **not** a route source — it is recall-oriented and
low-precision by design (see ``docs/architecture/v3-proposal.md``, "the
candidate miner"): it exists so that (a) call-based registrations invisible to
symbol/decorator extraction (Express-style ``router.get(path, handler)``, which
is a plain call, not a declaration) can still seed retrieval, and (b) the
verification layer can cross-check a submitted model's claims and ground
hallucination rejection — without maintaining a single framework-specific
token.

The only vocabulary here is the HTTP method names and generic routing words
(``route``, ``mapping``, ``path``, ...), which are common English/API
vocabulary shared across every framework's naming, not any one framework's
specific spelling (contrast with e.g. ``setGlobalPrefix(`` or ``@GetMapping``,
which name one specific framework).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Path-literal character class deliberately has no leading-slash requirement: some
# frameworks' routing calls take the leading "/" (Express, FastAPI, ...), others omit
# it by convention (Django's `path("users/", ...)`) — both are normalized to a
# leading "/" in `_normalize` below, so the *convention* difference never needs a
# framework name to handle.
_PATH_CHARS = r"[A-Za-z0-9_\-{}<>:./]*"
_VERB_LITERAL = re.compile(
    rf"""\b(get|post|put|patch|delete)\b\s*\(\s*["']({_PATH_CHARS})["']""",
    re.IGNORECASE,
)
# An HTTP verb immediately followed by the generic word "Mapping" is one compound
# identifier (`@GetMapping`, `@PostMapping`, ...) — a word-boundary check before
# "mapping" would never fire here since there's no non-word character between "Get"
# and "Mapping". Same vocabulary as _VERB_LITERAL (HTTP verb names), just annotated
# rather than called.
_VERB_MAPPING = re.compile(
    rf"""\b(get|post|put|patch|delete)mapping\b[^\n"']{{0,40}}["']({_PATH_CHARS})["']""",
    re.IGNORECASE,
)
# "mapping" as a bare word OR as the suffix of a longer identifier (`RequestMapping`)
# covers both styles without hardcoding either framework's exact annotation name.
_GENERIC_ROUTE_LITERAL = re.compile(
    rf"""(?:\b(?:route|api_view|re_path|url|path)\b|\w*mapping\b)[^\n"']{{0,40}}["']({_PATH_CHARS})["']""",
    re.IGNORECASE,
)
MAX_CANDIDATES_PER_FILE = 60


def _normalize(raw: str) -> str:
    raw = raw.strip()
    return raw if raw.startswith("/") else "/" + raw


@dataclass
class RouteCandidate:
    method: str   # "" when a verb couldn't be inferred generically
    path: str
    file: str
    line: int
    quote: str

    def to_doc(self) -> dict:
        return {"method": self.method, "path": self.path, "file": self.file,
                "line": self.line, "quote": self.quote}

    @classmethod
    def from_doc(cls, d: dict) -> "RouteCandidate":
        return cls(**d)


def mine_file_candidates(path: str, text: str) -> list[RouteCandidate]:
    """Scan one file's text for verb+path-literal shapes. Recall over precision."""
    out: list[RouteCandidate] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = _VERB_LITERAL.search(line)
        if m:
            out.append(RouteCandidate(m.group(1).upper(), _normalize(m.group(2)), path, i, line.strip()[:200]))
        elif (m := _VERB_MAPPING.search(line)):
            out.append(RouteCandidate(m.group(1).upper(), _normalize(m.group(2)), path, i, line.strip()[:200]))
        else:
            m2 = _GENERIC_ROUTE_LITERAL.search(line)
            if m2:
                out.append(RouteCandidate("", _normalize(m2.group(1)), path, i, line.strip()[:200]))
        if len(out) >= MAX_CANDIDATES_PER_FILE:
            break
    return out


def is_grounded_span(
    symbols, candidates: list[RouteCandidate], file: str, line_start: int, line_end: int, pad: int = 2
) -> bool:
    """True if ``file:line_start-line_end`` overlaps a real decorated/annotated symbol
    or a mined route candidate. Framework-blind grounding — no token list involved.
    ``symbols`` is any iterable of :class:`~postman_mcp.index.symbols.Symbol`.
    """
    for sym in symbols:
        if sym.file == file and sym.decorators and not (sym.line_end < line_start or sym.line_start > line_end):
            return True
    for c in candidates:
        if c.file == file and line_start - pad <= c.line <= line_end + pad:
            return True
    return False
