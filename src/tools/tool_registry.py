"""Tool registry — LLM function schemas and execution dispatcher."""

from __future__ import annotations

import json
from typing import Any

from src.core.logger import get_logger
from src.tools.filesystem import glob_files, grep_search, read_file
from src.tools.handoff import DelegateToAgentTool

logger = get_logger("tools.registry")

AGENT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": "Find files matching a glob pattern. Examples: '**/*.py', 'src/auth*', '**/test_*.py'",  # noqa: E501
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern to match files"}
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for text across project files. Returns matching lines with file paths and line numbers.",  # noqa: E501
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to search for"},
                    "path": {
                        "type": "string",
                        "description": "Subdirectory to limit search (e.g. 'src/')",
                        "default": "",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file's contents with line numbers. Optionally read a specific line range.",  # noqa: E501
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"},
                    "start_line": {
                        "type": "integer",
                        "description": "First line (1-indexed). Omit for start.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line (inclusive). Omit for end.",
                    },
                },
                "required": ["path"],
            },
        },
    },
]

_handoff_tool = DelegateToAgentTool()

_DISPATCH = {
    "glob_files": glob_files,
    "grep_search": grep_search,
    "read_file": read_file,
    "DelegateToAgent": _handoff_tool._execute
}


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool, return result as string for the LLM."""
    if "__" in tool_name:
        server_name = tool_name.split("__")[0]
        try:
            from src.core.config import ConfigManager
            from src.tools.mcp_client import MCPManager
            c = ConfigManager.get_instance().user
            mcp_servers = getattr(c, "mcp_servers", [])
            target_server = next((s for s in mcp_servers if s.get("name") == server_name), None)
            if target_server:
                logger.info(f"MCP Tool: {tool_name}({arguments})")
                return MCPManager.call_tool(target_server, tool_name, arguments)
        except Exception as e:
            logger.error(f"MCP Tool error: {e}")
            return json.dumps({"error": str(e)})

    func = _DISPATCH.get(tool_name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        logger.info(f"Tool: {tool_name}({arguments})")
        result = func(**arguments)
        return result if isinstance(result, str) else json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Tool error {tool_name}: {e}")
        return json.dumps({"error": str(e)})

_mcp_cache = None

def get_tool_definitions() -> list[dict]:
    global _mcp_cache
    tools = AGENT_TOOLS.copy()

    tools.append({
        "type": "function",
        "function": {
            "name": _handoff_tool.name,
            "description": _handoff_tool.description,
            "parameters": _handoff_tool.parameters,
        }
    })

    if _mcp_cache is None:
        _mcp_cache = []
        try:
            from src.core.config import ConfigManager
            c = ConfigManager.get_instance().user
            mcp_servers = getattr(c, "mcp_servers", [])
            if mcp_servers:
                from src.tools.mcp_client import MCPManager
                for s in mcp_servers:
                    if s.get("enabled", True):
                        discovered = MCPManager.discover(s)
                        _mcp_cache.extend(discovered)
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            _mcp_cache = []

    tools.extend(_mcp_cache)
    return tools
