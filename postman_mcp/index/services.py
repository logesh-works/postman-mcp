"""Service-unit discovery from build manifests — replaces framework *detection*.

A service unit is "a directory that builds/ships on its own", rooted wherever a
recognized manifest sits. No framework identification happens here: a Django
monolith, a Go microservice, and a NestJS workspace member are all just service
units with a root, a language hint, and a manifest path.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from postman_mcp.index.scanner import FileRecord

MANIFESTS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "package.json": "js",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
    "go.mod": "go",
    "composer.json": "php",
    "Gemfile": "ruby",
    "Cargo.toml": "rust",
}


@dataclass
class ServiceUnit:
    name: str
    root: str            # repo-relative posix dir; "" = repository root
    language: str
    manifest: str
    file_count: int = 0
    workspaces: list[str] = field(default_factory=list)  # declared members (package.json)

    def owns(self, path: str) -> bool:
        return path.startswith(self.root + "/") if self.root else True

    def to_doc(self) -> dict:
        return {
            "name": self.name, "root": self.root, "language": self.language,
            "manifest": self.manifest, "file_count": self.file_count,
            "workspaces": self.workspaces,
        }

    @classmethod
    def from_doc(cls, d: dict) -> "ServiceUnit":
        return cls(**d)


def discover_services(root: Path, files: list[FileRecord]) -> list[ServiceUnit]:
    """Root a service unit at every manifest directory; nearest root wins ownership."""
    units: dict[str, ServiceUnit] = {}
    known = {f.path for f in files}

    for manifest_name, language in MANIFESTS.items():
        for path in _manifest_paths(root, manifest_name, known):
            unit_dir = "/".join(path.split("/")[:-1])
            if unit_dir in units:
                continue  # first manifest for a dir wins (dict order of MANIFESTS)
            name = unit_dir.split("/")[-1] if unit_dir else root.resolve().name
            unit = ServiceUnit(name=name, root=unit_dir, language=language, manifest=path)
            if manifest_name == "package.json":
                unit.workspaces = _package_workspaces(root / path)
            units[unit_dir] = unit

    if not units:
        units[""] = ServiceUnit(name=root.resolve().name, root="", language="", manifest="")

    # Assign each code file to its nearest (longest-root) unit.
    ordered = sorted(units.values(), key=lambda u: len(u.root), reverse=True)
    for f in files:
        if not f.language:
            continue
        for unit in ordered:
            if unit.owns(f.path):
                unit.file_count += 1
                break
    return sorted(units.values(), key=lambda u: u.root)


def _manifest_paths(root: Path, manifest_name: str, known: set[str]) -> list[str]:
    """Locate manifests. Scanner only inventories code/corpus files, so look on disk."""
    found: list[str] = []
    if (root / manifest_name).is_file():
        found.append(manifest_name)
    # One level of nesting covers the common monorepo layouts (services/*, packages/*)
    # without a full recursive walk; deeper units still appear via their code files'
    # nearest-root assignment when a manifest exists at depth 2.
    for depth in ("*", "*/*"):
        for p in root.glob(f"{depth}/{manifest_name}"):
            if p.is_file() and not _ignored(p, root):
                found.append(p.relative_to(root).as_posix())
    return sorted(set(found))


def _ignored(path: Path, root: Path) -> bool:
    from postman_mcp.index.scanner import DEFAULT_IGNORED_DIRS

    parts = path.relative_to(root).parts
    return any(part in DEFAULT_IGNORED_DIRS or part.startswith(".") for part in parts[:-1])


def _package_workspaces(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    ws = data.get("workspaces")
    if isinstance(ws, dict):
        ws = ws.get("packages", [])
    return ws if isinstance(ws, list) else []
