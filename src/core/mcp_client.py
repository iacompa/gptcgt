"""
Model Context Protocol (MCP) client for connecting to external tools and services.

Supports both stdio and HTTP transports. Discovers tools from MCP servers
and converts them to LLM function call schemas that can be injected
into agent context.
"""

from __future__ import annotations

import asyncio
import json
import subprocess  # noqa: F401
from dataclasses import dataclass, field
from typing import Any

from src.core.logger import get_logger

logger = get_logger("core.mcp_client")


@dataclass
class MCPToolSchema:
    """Schema for a tool discovered from an MCP server."""

    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    server_name: str = ""

    def to_openai_function(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": f"mcp_{self.server_name}_{self.name}",
                "description": f"[MCP:{self.server_name}] {self.description}",
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    transport: str = "stdio"  # "stdio" or "http"
    command: str = ""  # For stdio: command to start the server
    args: list[str] = field(default_factory=list)
    url: str = ""  # For HTTP: server URL
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> MCPServerConfig:
        """Create from a dictionary (e.g., from config file)."""
        return cls(
            name=data.get("name", "unknown"),
            transport=data.get("transport", "stdio"),
            command=data.get("command", ""),
            args=data.get("args", []),
            url=data.get("url", ""),
            env=data.get("env", {}),
            enabled=data.get("enabled", True),
        )


class MCPClient:
    """
    Client for connecting to MCP servers and exposing their tools to agents.

    Usage:
        client = MCPClient()

        # Connect to a server
        await client.connect(MCPServerConfig(
            name="github",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "..."},
        ))

        # Get tools for injection into LLM context
        tools = client.get_all_tool_schemas()

        # Execute a tool call
        result = await client.call_tool("mcp_github_search_repos", {"query": "python"})
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConnection] = {}
        self._tools: dict[str, MCPToolSchema] = {}

    async def connect(self, config: MCPServerConfig) -> bool:
        """
        Connect to an MCP server.  # noqa: D213

        Args:
            config: Server configuration.

        Returns:  # noqa: D413
            True if connection succeeded.

        """
        if not config.enabled:
            logger.info(f"MCP server '{config.name}' is disabled, skipping.")
            return False

        try:
            if config.transport == "stdio":
                conn = StdioMCPConnection(config)
            elif config.transport == "http":
                conn = HttpMCPConnection(config)
            else:
                logger.error(f"Unknown MCP transport: {config.transport}")
                return False

            await conn.initialize()
            self._servers[config.name] = conn

            # Discover tools
            tools = await conn.list_tools()
            for tool in tools:
                tool.server_name = config.name
                key = f"mcp_{config.name}_{tool.name}"
                self._tools[key] = tool

            logger.info(
                f"MCP server '{config.name}' connected with {len(tools)} tools: "
                f"{[t.name for t in tools]}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{config.name}': {e}")
            return False

    async def disconnect(self, server_name: str) -> None:
        """Disconnect from an MCP server."""
        conn = self._servers.pop(server_name, None)
        if conn:
            await conn.close()
            # Remove tools from this server
            keys_to_remove = [k for k, v in self._tools.items() if v.server_name == server_name]
            for k in keys_to_remove:
                del self._tools[k]
            logger.info(f"MCP server '{server_name}' disconnected.")

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for name in list(self._servers.keys()):
            await self.disconnect(name)

    def get_all_tool_schemas(self) -> list[dict]:
        """Get all MCP tools in OpenAI function calling format."""
        return [tool.to_openai_function() for tool in self._tools.values()]

    def get_tool_names(self) -> list[str]:
        """Get names of all connected MCP tools."""
        return list(self._tools.keys())

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Execute an MCP tool call.  # noqa: D213

        Args:
            tool_name: The full tool name (e.g., "mcp_github_search_repos").
            arguments: Tool arguments.

        Returns:  # noqa: D413
            Tool result as a string.

        """
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"Unknown MCP tool: {tool_name}"})

        conn = self._servers.get(tool.server_name)
        if not conn:
            return json.dumps({"error": f"MCP server '{tool.server_name}' not connected"})

        try:
            result = await conn.call_tool(tool.name, arguments)
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        except Exception as e:
            logger.error(f"MCP tool call failed: {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool name belongs to an MCP server."""
        return tool_name.startswith("mcp_") and tool_name in self._tools


class MCPServerConnection:
    """Base class for MCP server connections."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config

    async def initialize(self) -> None:
        """Initialize the connection and perform handshake."""
        raise NotImplementedError

    async def list_tools(self) -> list[MCPToolSchema]:
        """List available tools from the server."""
        raise NotImplementedError

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool on the server."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close the connection."""
        raise NotImplementedError


class StdioMCPConnection(MCPServerConnection):
    """MCP connection via stdio (subprocess)."""

    def __init__(self, config: MCPServerConfig) -> None:
        super().__init__(config)
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0

    async def initialize(self) -> None:
        """Start the subprocess and send initialize request."""
        env = {**dict(__import__("os").environ), **self.config.env}
        cmd = [self.config.command] + self.config.args

        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Send JSON-RPC initialize
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "gptcgt", "version": "1.0.0"},
        })
        logger.debug(f"MCP initialize response: {response}")

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

    async def list_tools(self) -> list[MCPToolSchema]:
        """List tools from the MCP server."""
        response = await self._send_request("tools/list", {})
        tools = []
        for tool_data in response.get("tools", []):
            tools.append(MCPToolSchema(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
            ))
        return tools

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool via JSON-RPC."""
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        # Extract content from MCP response
        content = response.get("content", [])
        if content and isinstance(content, list):
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            return "\n".join(texts) if texts else str(content)
        return response

    async def _send_request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise ConnectionError("MCP subprocess not running")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }

        msg = json.dumps(request) + "\n"
        self._process.stdin.write(msg.encode())
        await self._process.stdin.drain()

        # Read response line
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            if line:
                response = json.loads(line.decode())
                if "error" in response:
                    raise Exception(f"MCP error: {response['error']}")
                return response.get("result", {})
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP request timed out: {method}")

        return {}

    async def _send_notification(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        msg = json.dumps(notification) + "\n"
        self._process.stdin.write(msg.encode())
        await self._process.stdin.drain()

    async def close(self) -> None:
        """Terminate the subprocess."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()


class HttpMCPConnection(MCPServerConnection):
    """MCP connection via HTTP (SSE/streamable-http)."""

    def __init__(self, config: MCPServerConfig) -> None:
        super().__init__(config)
        self._session = None

    async def initialize(self) -> None:
        """Initialize HTTP connection."""
        try:
            import httpx
            self._session = httpx.AsyncClient(
                base_url=self.config.url,
                timeout=30.0,
            )
            # Send initialize
            response = await self._session.post("/initialize", json={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gptcgt", "version": "1.0.0"},
            })
            response.raise_for_status()
            logger.debug(f"MCP HTTP initialize: {response.status_code}")
        except ImportError:
            logger.warning("httpx not installed — HTTP MCP transport unavailable")
            raise

    async def list_tools(self) -> list[MCPToolSchema]:
        """List tools via HTTP."""
        if not self._session:
            return []
        response = await self._session.post("/tools/list", json={})
        data = response.json()
        return [
            MCPToolSchema(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in data.get("tools", [])
        ]

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool via HTTP."""
        if not self._session:
            return {"error": "Not connected"}
        response = await self._session.post("/tools/call", json={
            "name": name,
            "arguments": arguments,
        })
        return response.json()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.aclose()
