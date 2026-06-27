"""Input resolution — OpenAPI first, code parsing as fallback."""

from postman_mcp.input.detect import (
    DetectedProject,
    detect_framework,
    detect_openapi_source,
    detect_project,
)

__all__ = [
    "DetectedProject",
    "detect_framework",
    "detect_openapi_source",
    "detect_project",
]
