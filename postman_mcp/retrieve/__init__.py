"""The V3 retrieval layer — graph slicing + token budgeting + context assembly.

Public surface: :func:`postman_mcp.retrieve.assembler.assemble_context` and
:func:`postman_mcp.retrieve.assembler.index_summary`.
"""

from postman_mcp.retrieve.assembler import SliceError, assemble_context, index_summary

__all__ = ["assemble_context", "index_summary", "SliceError"]
