"""Setup helpers used by ``init``/``doctor``: MCP registration + slash-command install.

Both mechanisms are handled automatically so the user never hand-edits config.
"""

from postman_mcp.setup.installer import (
    COMMAND_NAMES,
    commands_dir,
    install_slash_commands,
    slash_commands_present,
)
from postman_mcp.setup.registration import (
    ensure_gitignore,
    is_server_registered,
    register_mcp_server,
)

__all__ = [
    "COMMAND_NAMES",
    "commands_dir",
    "install_slash_commands",
    "slash_commands_present",
    "ensure_gitignore",
    "is_server_registered",
    "register_mcp_server",
]
