"""Postman MCP — sync API code into Postman collections from Claude Code.

See ``postman-mcp-prd-v3.md`` for the product spec. Public entry points:
- ``postman_mcp.cli:main`` — the ``postman-mcp`` terminal command (PRD §B).
- ``postman_mcp.server`` — the stdio MCP server booted by ``postman-mcp serve`` (§5).
"""

__version__ = "0.1.0"
