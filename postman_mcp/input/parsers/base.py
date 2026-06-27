"""Shared helpers for code parsers (PRD §9.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from postman_mcp.models import FieldType

# Skip vendored / build dirs when scanning a project.
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
    ".mypy_cache", ".pytest_cache", "site-packages", ".tox",
}


def iter_source_files(root: Path | str, suffixes: tuple[str, ...]) -> Iterator[Path]:
    """Yield project source files with the given suffixes, skipping vendor dirs."""
    root = Path(root)
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix in suffixes:
            yield path


# Map Python annotation / TS type names to coarse field types (PRD §8.3).
_PY_TYPE_MAP = {
    "str": FieldType.STRING,
    "int": FieldType.INTEGER,
    "float": FieldType.NUMBER,
    "bool": FieldType.BOOLEAN,
    "list": FieldType.ARRAY,
    "dict": FieldType.OBJECT,
    "datetime": FieldType.STRING,
    "date": FieldType.STRING,
    "uuid": FieldType.STRING,
    "decimal": FieldType.NUMBER,
}

_TS_TYPE_MAP = {
    "string": FieldType.STRING,
    "number": FieldType.NUMBER,
    "boolean": FieldType.BOOLEAN,
    "any": FieldType.UNKNOWN,
    "date": FieldType.STRING,
}


def py_field_type(annotation: str) -> FieldType:
    return _PY_TYPE_MAP.get(annotation.strip().lower(), FieldType.UNKNOWN)


def ts_field_type(annotation: str) -> FieldType:
    ann = annotation.strip().lower().rstrip("[]")
    if annotation.strip().endswith("[]"):
        return FieldType.ARRAY
    return _TS_TYPE_MAP.get(ann, FieldType.UNKNOWN)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:  # pragma: no cover - defensive
        return ""
