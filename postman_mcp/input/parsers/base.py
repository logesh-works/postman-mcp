"""Shared helpers for code parsers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, Optional

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


def iter_given_files(
    root: Path | str, paths: Iterable[str], suffixes: tuple[str, ...]
) -> Iterator[Path]:
    """Yield only the given files, resolved relative to ``root`` and filtered to
    ``suffixes`` — used for incremental syncs so a parser walks just the files git
    reports as changed instead of re-scanning the whole project.
    """
    root = Path(root)
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        if path.suffix not in suffixes or not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        yield path


def source_files(
    root: Path | str, suffixes: tuple[str, ...], only_files: Optional[Iterable[str]]
) -> Iterator[Path]:
    """``iter_given_files`` when ``only_files`` is given, else the full project scan."""
    if only_files is None:
        return iter_source_files(root, suffixes)
    return iter_given_files(root, only_files, suffixes)


# Map Python annotation / TS type names to coarse field types.
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
