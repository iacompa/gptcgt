import sys

import pytest

from src.core.mcp_client import MCPManager

MOCK_SERVER_SCRIPT = """\
import json
import sys

while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        req = json.loads(line)
        method = req.get("method")

        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": req["id"], "result": {}}
            sys.stdout.write(json.dumps(resp) + "\\n")
            sys.stdout.flush()
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {"tools": [{"name": "fake_tool"}]},
            }
            sys.stdout.write(json.dumps(resp) + "\\n")
            sys.stdout.flush()
        elif method == "tools/call":
            resp = {
                "jsonrpc": "2.0",
                "id": req["id"],
                "result": {"content": "hello from mock"},
            }
            sys.stdout.write(json.dumps(resp) + "\\n")
            sys.stdout.flush()
    except Exception:
        pass
"""


@pytest.fixture
def mocked_mcp_server(tmp_path):
    script = tmp_path / "mock_mcp.py"
    script.write_text(MOCK_SERVER_SCRIPT)
    return {"name": "mocked", "command": sys.executable, "args": [str(script)]}


def test_mcp_discover(mocked_mcp_server):
    tools = MCPManager.discover(mocked_mcp_server)
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "mocked__fake_tool"


def test_mcp_call(mocked_mcp_server):
    res = MCPManager.call_tool(mocked_mcp_server, "mocked__fake_tool", {"arg": "val"})
    assert "hello" in res
