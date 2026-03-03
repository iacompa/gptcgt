"""Lightweight synchronous JSON-RPC 2.0 MCP Client over stdio."""

import json
import os
import select
import subprocess

from src.core.logger import get_logger

logger = get_logger("tools.mcp_client")

# Default timeout (seconds) for reading a line from the MCP server process.
MCP_READ_TIMEOUT = 30


def _readline_with_timeout(proc: subprocess.Popen, timeout: float = MCP_READ_TIMEOUT) -> str:
    """
    Read a single line from *proc.stdout* with a timeout.

    Uses ``select`` to avoid blocking indefinitely when the child process
    never writes an expected response (e.g. unknown method, hung server).

    Returns an empty string when the process closes stdout or the timeout expires.
    """
    fd = proc.stdout.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if ready:
        return proc.stdout.readline()
    logger.warning("MCP read timed out after %ss", timeout)
    return ""


class MCPManager:
    """Lightweight synchronous JSON-RPC 2.0 MCP Client over stdio."""

    @classmethod
    def _start_process(cls, server_cfg: dict) -> subprocess.Popen:
        cmd = server_cfg.get("command")
        args = server_cfg.get("args", [])
        env = server_cfg.get("env", {})

        full_env = os.environ.copy()
        full_env.update(env)

        if not cmd:
            raise ValueError("No command specified for MCP server")

        return subprocess.Popen(
            [cmd] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            text=True,
            bufsize=1,
        )

    @classmethod
    def _initialize(cls, proc: subprocess.Popen) -> None:
        """Perform the MCP initialize handshake."""
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "gptcgt", "version": "0.1.0"},
                "protocolVersion": "2024-11-05",
                "capabilities": {},
            },
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write(json.dumps(notify) + "\n")
        proc.stdin.flush()

        while True:
            line = _readline_with_timeout(proc)
            if not line:
                raise RuntimeError("MCP process died or timed out during init")
            try:
                msg = json.loads(line)
                if msg.get("id") == 1:
                    return
            except ValueError:
                continue

    @classmethod
    def discover(cls, server_cfg: dict) -> list[dict]:
        proc = cls._start_process(server_cfg)
        try:
            cls._initialize(proc)

            tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            proc.stdin.write(json.dumps(tools_req) + "\n")
            proc.stdin.flush()

            tools: list[dict] = []
            while True:
                line = _readline_with_timeout(proc)
                if not line:
                    break
                try:
                    msg = json.loads(line)
                    if msg.get("id") == 2:
                        mcp_tools = msg.get("result", {}).get("tools", [])
                        prefix = server_cfg.get("name", "mcp")
                        for mt in mcp_tools:
                            tools.append({
                                "type": "function",
                                "function": {
                                    "name": f"{prefix}__{mt['name']}",
                                    "description": mt.get("description", ""),
                                    "parameters": mt.get("inputSchema", {}),
                                },
                            })
                        break
                except ValueError:
                    continue
            return tools
        finally:
            proc.terminate()

    @classmethod
    def call_tool(cls, server_cfg: dict, tool_name: str, arguments: dict) -> str:
        proc = cls._start_process(server_cfg)
        try:
            cls._initialize(proc)

            call_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name.split("__", 1)[-1],
                    "arguments": arguments,
                },
            }
            proc.stdin.write(json.dumps(call_req) + "\n")
            proc.stdin.flush()

            while True:
                line = _readline_with_timeout(proc)
                if not line:
                    return "Error: MCP Process Terminated Unexpectedly or Timed Out"
                try:
                    msg = json.loads(line)
                    if msg.get("id") == 3:
                        res = msg.get("result", {})
                        if res.get("isError"):
                            return f"Error: {res.get('content')}"
                        return json.dumps(res.get("content"))
                except ValueError:
                    pass
        except Exception as e:
            return f"Error executing MCP tool: {e!s}"
        finally:
            proc.terminate()
