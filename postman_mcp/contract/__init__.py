"""The provider-agnostic contract between any LLM and the MCP server.

This package holds the Canonical API Model (APIM) schema
(:mod:`postman_mcp.contract.schema`) and the ``get_contract`` publication surface
(:mod:`postman_mcp.contract.publish`).
"""

from postman_mcp.contract.schema import ApiModel

__all__ = ["ApiModel"]
