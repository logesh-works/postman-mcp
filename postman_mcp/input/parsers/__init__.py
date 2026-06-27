"""Code-parsing fallback parsers. Dispatch by framework.

Used when no OpenAPI spec covers a route. Each parser emits the same normalized
``RouteModel`` as the OpenAPI path, tagged ``source=code``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from postman_mcp.models import RouteModel


def parse_framework(
    framework: Optional[str], project_root: Path | str
) -> tuple[list[RouteModel], list[str]]:
    """Dispatch to the framework parser; returns ``(routes, skipped)``."""
    if not framework:
        return [], []
    fw = framework.lower()
    if fw == "fastapi":
        from postman_mcp.input.parsers.fastapi import parse

        return parse(project_root)
    if fw == "express":
        from postman_mcp.input.parsers.express import parse

        return parse(project_root)
    if fw == "django":
        from postman_mcp.input.parsers.django import parse

        return parse(project_root)
    if fw == "nestjs":
        from postman_mcp.input.parsers.nestjs import parse

        return parse(project_root)
    return [], []
