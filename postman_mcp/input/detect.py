"""Detect the project's framework and OpenAPI source.

Used by ``init`` to seed ``config.framework`` / ``config.inputMode`` /
``config.openApiSource``, and re-used by the resolver at sync time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel

# Frameworks supported.
FRAMEWORKS = ("fastapi", "express", "django", "nestjs", "flask", "spring")

# Conventional committed spec filenames, in priority order.
_SPEC_FILENAMES = (
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
    "api-docs.json",
)

# Well-known live spec endpoints by framework, in priority order. Express and Django
# have no single convention, so several common ones are listed; ``init`` probes them
# and keeps the first that responds with a valid spec. (FastAPI/NestJS serve one each.)
LIVE_SPEC_ENDPOINTS: dict[str, list[str]] = {
    "fastapi": ["http://localhost:8000/openapi.json"],
    "nestjs": ["http://localhost:3000/api-json"],
    "express": [
        "http://localhost:3000/api-docs.json",
        "http://localhost:3000/swagger.json",
        "http://localhost:3000/openapi.json",
        "http://localhost:8000/api-docs.json",
    ],
    "django": [
        "http://localhost:8000/api/schema/",
        "http://localhost:8000/swagger.json",
        "http://localhost:8000/openapi.json",
    ],
}


class DetectedProject(BaseModel):
    framework: Optional[str] = None
    input_mode: str = "code"
    openapi_source: Optional[str] = None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def detect_framework(project_root: Path | str = ".") -> Optional[str]:
    """Detect framework by signature files.

    FastAPI: ``main.py`` + a ``fastapi`` import · Express: ``package.json`` + express ·
    Django: ``manage.py`` · NestJS: ``@nestjs/core`` in ``package.json``.
    """
    root = Path(project_root)

    # Python signatures
    if (root / "manage.py").exists():
        return "django"

    py_files = list(root.rglob("*.py"))
    for py in py_files[:200]:  # bound the scan
        text = _read(py)
        low = text.lower()
        if "fastapi" in low and ("FastAPI(" in text or "from fastapi" in text):
            return "fastapi"
        if "flask" in low and ("Flask(" in text or "from flask" in text):
            return "flask"

    # JS/TS signatures
    pkg = root / "package.json"
    if pkg.exists():
        text = _read(pkg)
        if "@nestjs/core" in text:
            return "nestjs"
        if '"express"' in text or "'express'" in text:
            return "express"

    # Java / Spring signatures
    if (root / "pom.xml").exists() or list(root.rglob("build.gradle")):
        for java in list(root.rglob("*.java"))[:200]:
            text = _read(java)
            if "@RestController" in text or "@SpringBootApplication" in text or "@Controller" in text:
                return "spring"

    # Django without manage.py at root (settings present)
    if list(root.rglob("settings.py")):
        return "django"
    return None


def detect_committed_spec(project_root: Path | str = ".") -> Optional[str]:
    """Find a committed spec file on disk. No network. Returns a path or ``None``.

    Kept separate from live-endpoint suggestion so the resolver can always honor a
    committed spec at sync time without ever touching the network.
    """
    root = Path(project_root)
    for name in _SPEC_FILENAMES:
        candidate = root / name
        if candidate.exists():
            return str(candidate)
    # Conventional nested locations
    for name in _SPEC_FILENAMES:
        matches = list(root.rglob(name))
        if matches:
            return str(matches[0])
    return None


def live_spec_candidates(framework: Optional[str]) -> list[str]:
    """Common live spec URLs to probe for a framework (empty if none known)."""
    return list(LIVE_SPEC_ENDPOINTS.get(framework or "", []))


def verify_live_spec(
    candidates: list[str], *, timeout: float = 1.5
) -> Optional[str]:
    """Return the first candidate URL that serves a valid OpenAPI doc, or ``None``.

    Best-effort and fast-failing: a refused connection (server not running) returns
    immediately, so probing a few localhost URLs at ``init`` time is cheap. Used to make
    OpenAPI-first actually kick in for frameworks that serve a spec live (Express, etc.)
    instead of silently falling back to code parsing.
    """
    from postman_mcp.input import openapi as openapi_mod

    for url in candidates:
        try:
            spec = openapi_mod.load_spec(url, timeout=timeout)
        except openapi_mod.OpenApiError:
            continue
        if isinstance(spec, dict) and spec.get("paths"):
            return url
    return None


def detect_openapi_source(
    project_root: Path | str = ".",
    framework: Optional[str] = None,
) -> Optional[str]:
    """Find a committed spec file or *suggest* the first known live endpoint.

    Returns a path or URL, or ``None`` if nothing is discoverable. Committed files win
    (they need no network); a live URL is only a suggestion ``init`` later probes.
    """
    committed = detect_committed_spec(project_root)
    if committed:
        return committed
    candidates = live_spec_candidates(framework)
    return candidates[0] if candidates else None


def detect_project(project_root: Path | str = ".") -> DetectedProject:
    """Full detection: framework + input mode + openapi source."""
    framework = detect_framework(project_root)
    source = detect_openapi_source(project_root, framework)
    # A committed spec file means openapi mode for sure; a suggested live endpoint is
    # treated as openapi too but re-checked for freshness each sync.
    input_mode = "openapi" if source else "code"
    return DetectedProject(
        framework=framework, input_mode=input_mode, openapi_source=source
    )
