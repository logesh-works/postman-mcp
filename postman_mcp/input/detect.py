"""Detect the project's framework and OpenAPI source.

Used by ``init`` to seed ``config.framework`` / ``config.inputMode`` /
``config.openApiSource``, and re-used by the resolver at sync time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel

# Frameworks supported in the MVP.
FRAMEWORKS = ("fastapi", "express", "django", "nestjs")

# Conventional committed spec filenames, in priority order.
_SPEC_FILENAMES = (
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
)

# Well-known live spec endpoints by framework.
LIVE_SPEC_ENDPOINTS = {
    "fastapi": "http://localhost:8000/openapi.json",
    "nestjs": "http://localhost:3000/api-json",
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
        if "fastapi" in text.lower() and ("FastAPI(" in text or "from fastapi" in text):
            return "fastapi"

    # JS/TS signatures
    pkg = root / "package.json"
    if pkg.exists():
        text = _read(pkg)
        if "@nestjs/core" in text:
            return "nestjs"
        if '"express"' in text or "'express'" in text:
            return "express"

    # Django without manage.py at root (settings present)
    if list(root.rglob("settings.py")):
        return "django"
    return None


def detect_openapi_source(
    project_root: Path | str = ".",
    framework: Optional[str] = None,
) -> Optional[str]:
    """Find a committed spec file or known live endpoint.

    Returns a path or URL, or ``None`` if no spec is discoverable statically. (Live
    endpoints are only *suggested* here; the resolver verifies reachability at §9.2.)
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
    # Suggest a live endpoint for frameworks that serve one (verified later).
    if framework in LIVE_SPEC_ENDPOINTS:
        return LIVE_SPEC_ENDPOINTS[framework]
    return None


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
