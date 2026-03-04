"""
MCP Client with connection pooling.

Maintains live process handles per MCP server to avoid spawning a new
subprocess for every discover/call. Processes are reused across calls
and cleaned up on shutdown.
"""

import json
import os
import select
import subprocess
import threading

from src.core.logger import get_logger

logger = get_logger("tools.mcp_client")

# Default timeout (seconds) for reading a line from the MCP server process.
MCP_READ_TIMEOUT = 30


def _readline_with_timeout(proc: subprocess.Popen, timeout: float = MCP_READ_TIMEOUT) -> str:
    """
    Read a single line from *proc.stdout* with a timeout.

    Uses ``select`` to avoid blocking indefinitely when the child process
    never writes an expected response (e.g. unknown method, hung server).
    """
    fd = proc.stdout.fileno()
    ready, _, _ = select.select([fd], [], [], timeout)
    if ready:
        return proc.stdout.readline()
    logger.warning("MCP read timed out after %ss", timeout)
    return ""


class MCPConnectionPool:
    """
    Maintains a pool of live MCP server processes, keyed by server name.

    Reuses existing connections instead of spawning a new subprocess
    for every discover/call_tool invocation.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._pool: dict[str, subprocess.Popen] = {}
                    cls._instance._id_counters: dict[str, int] = {}
        return cls._instance

    def _server_key(self, server_cfg: dict) -> str:
        return server_cfg.get("name", server_cfg.get("command", "unknown"))

    def get_or_create(self, server_cfg: dict) -> subprocess.Popen:
        """Get an existing connection or create a new one."""
        key = self._server_key(server_cfg)

        with self._lock:
            proc = self._pool.get(key)
            if proc and proc.poll() is None:
                # Process is still alive
                return proc

            # Process is dead or doesn't exist — start a new one
            if proc and proc.poll() is not None:
                logger.info(f"MCP process for '{key}' died (rc={proc.poll()}), restarting")

            proc = self._start_and_init(server_cfg)
            self._pool[key] = proc
            self._id_counters[key] = 10  # Start IDs at 10 for pooled connections
            return proc

    def _start_and_init(self, server_cfg: dict) -> subprocess.Popen:
        """Spawn the MCP server process and perform the initialize handshake."""
        cmd = server_cfg.get("command")
        args = server_cfg.get("args", [])
        env = server_cfg.get("env", {})

        full_env = os.environ.copy()
        full_env.update(env)

        if not cmd:
            raise ValueError("No command specified for MCP server")

        proc = subprocess.Popen(
            [cmd] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=full_env,
            text=True,
            bufsize=1,
        )

        # Initialize handshake
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
                proc.terminate()
                raise RuntimeError("MCP process died or timed out during init")
            try:
                msg = json.loads(line)
                if msg.get("id") == 1:
                    break
            except ValueError:
                continue

        logger.info(f"MCP connection established for '{self._server_key(server_cfg)}'")
        return proc

    def next_id(self, server_cfg: dict) -> int:
        """Get the next JSON-RPC request ID for this server."""
        key = self._server_key(server_cfg)
        with self._lock:
            self._id_counters.setdefault(key, 10)
            self._id_counters[key] += 1
            return self._id_counters[key]

    def close(self, server_cfg: dict) -> None:
        """Terminate a specific server connection."""
        key = self._server_key(server_cfg)
        with self._lock:
            proc = self._pool.pop(key, None)
            if proc and proc.poll() is None:
                proc.terminate()
                logger.info(f"Closed MCP connection for '{key}'")

    def close_all(self) -> None:
        """Terminate all pooled connections (call on app shutdown)."""
        with self._lock:
            for key, proc in self._pool.items():
                if proc.poll() is None:
                    proc.terminate()
                    logger.info(f"Closed MCP connection for '{key}'")
            self._pool.clear()
            self._id_counters.clear()


class MCPManager:
    """MCP Client with connection pooling via MCPConnectionPool."""

    _pool = MCPConnectionPool()

    @classmethod
    def discover(cls, server_cfg: dict) -> list[dict]:
        """Discover available tools from an MCP server."""
        try:
            proc = cls._pool.get_or_create(server_cfg)
            req_id = cls._pool.next_id(server_cfg)

            tools_req = {"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": {}}
            proc.stdin.write(json.dumps(tools_req) + "\n")
            proc.stdin.flush()

            tools: list[dict] = []
            while True:
                line = _readline_with_timeout(proc)
                if not line:
                    # Connection may have died — invalidate and retry once
                    cls._pool.close(server_cfg)
                    return cls._discover_fresh(server_cfg)
                try:
                    msg = json.loads(line)
                    if msg.get("id") == req_id:
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
        except Exception as e:
            logger.error(f"MCP discover failed: {e}")
            cls._pool.close(server_cfg)
            return []

    @classmethod
    def _discover_fresh(cls, server_cfg: dict) -> list[dict]:
        """Retry discover with a fresh connection (called once if pooled conn dies)."""
        try:
            proc = cls._pool.get_or_create(server_cfg)
            req_id = cls._pool.next_id(server_cfg)

            tools_req = {"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": {}}
            proc.stdin.write(json.dumps(tools_req) + "\n")
            proc.stdin.flush()

            tools: list[dict] = []
            while True:
                line = _readline_with_timeout(proc)
                if not line:
                    break
                try:
                    msg = json.loads(line)
                    if msg.get("id") == req_id:
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
        except Exception as e:
            logger.error(f"MCP discover retry failed: {e}")
            return []

    @classmethod
    def call_tool(cls, server_cfg: dict, tool_name: str, arguments: dict) -> str:
        """Call a tool on an MCP server via the pooled connection."""
        try:
            proc = cls._pool.get_or_create(server_cfg)
            req_id = cls._pool.next_id(server_cfg)

            call_req = {
                "jsonrpc": "2.0",
                "id": req_id,
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
                    # Connection died — retry with fresh
                    cls._pool.close(server_cfg)
                    return cls._call_tool_fresh(server_cfg, tool_name, arguments)
                try:
                    msg = json.loads(line)
                    if msg.get("id") == req_id:
                        res = msg.get("result", {})
                        if res.get("isError"):
                            return f"Error: {res.get('content')}"
                        return json.dumps(res.get("content"))
                except ValueError:
                    pass
        except Exception as e:
            cls._pool.close(server_cfg)
            return f"Error executing MCP tool: {e!s}"

    @classmethod
    def _call_tool_fresh(cls, server_cfg: dict, tool_name: str, arguments: dict) -> str:
        """Retry call_tool with a fresh connection."""
        try:
            proc = cls._pool.get_or_create(server_cfg)
            req_id = cls._pool.next_id(server_cfg)

            call_req = {
                "jsonrpc": "2.0",
                "id": req_id,
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
                    if msg.get("id") == req_id:
                        res = msg.get("result", {})
                        if res.get("isError"):
                            return f"Error: {res.get('content')}"
                        return json.dumps(res.get("content"))
                except ValueError:
                    pass
        except Exception as e:
            return f"Error executing MCP tool (retry): {e!s}"

    @classmethod
    def close_all(cls) -> None:
        """Shut down all pooled connections. Call on app teardown."""
        cls._pool.close_all()
