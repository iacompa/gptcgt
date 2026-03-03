import json  # noqa: I001
import subprocess
import os
import threading  # noqa: F401
from typing import Any  # noqa: F401

from src.core.logger import get_logger

logger = get_logger("tools.mcp_client")

class MCPManager:
    """Lightweight synchronous JSON-RPC 2.0 MCP Client over stdio."""

    @classmethod
    def discover(cls, server_cfg: dict) -> list[dict]:
        cmd = server_cfg.get("command")
        args = server_cfg.get("args", [])
        env = server_cfg.get("env", {})
  # noqa: W293
        full_env = os.environ.copy()
        full_env.update(env)
  # noqa: W293
        if not cmd:
            raise ValueError("No command specified for MCP server")

        proc = subprocess.Popen(
            [cmd] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            text=True,
            bufsize=1
        )
        try:
            # Initialize
            init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "gptcgt", "version": "0.1.0"}, "protocolVersion": "2024-11-05", "capabilities": {}}}  # noqa: E501
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
  # noqa: W293
            # Wait for init
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError("MCP process died during init")
                try:
                    msg = json.loads(line)
                    if msg.get("id") == 1:
                        break
                except ValueError:
                    continue
  # noqa: W293
            # Tools List
            tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            proc.stdin.write(json.dumps(tools_req) + "\n")
            proc.stdin.flush()
  # noqa: W293
            tools = []
            while True:
                line = proc.stdout.readline()
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
                                    "parameters": mt.get("inputSchema", {})
                                }
                            })
                        break
                except ValueError:
                    continue
            return tools
        finally:
            proc.terminate()

    @classmethod
    def call_tool(cls, server_cfg: dict, tool_name: str, arguments: dict) -> str:
        cmd = server_cfg.get("command")
        args = server_cfg.get("args", [])
        env = server_cfg.get("env", {})
        full_env = os.environ.copy()
        full_env.update(env)
  # noqa: W293
        proc = subprocess.Popen(
            [cmd] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            text=True,
            bufsize=1
        )
        try:
            init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "gptcgt", "version": "0.1.0"}, "protocolVersion": "2024-11-05", "capabilities": {}}}  # noqa: E501
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
  # noqa: W293
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError("MCP process died")
                try:
                    msg = json.loads(line)
                    if msg.get("id") == 1:
                        break
                except ValueError:
                    pass

            call_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name.split("__", 1)[-1],
                    "arguments": arguments
                }
            }
            proc.stdin.write(json.dumps(call_req) + "\n")
            proc.stdin.flush()
  # noqa: W293
            while True:
                line = proc.stdout.readline()
                if not line:
                    return "Error: MCP Process Terminated Unexpectedly"
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
            return f"Error executing MCP tool: {str(e)}"
        finally:
            proc.terminate()
