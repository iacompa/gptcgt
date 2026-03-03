import pytest

from src.tools.mcp_client import MCPManager


@pytest.fixture
def mocked_mcp_server(tmp_path):
    # Create a wrapper dummy python script that acts like an MCP server
    script = tmp_path / "mock_mcp.py"
    script.write_text("""import sys, json
while True:
    try:
        line = sys.stdin.readline()
        if not line: break
        req = json.loads(line)
        if req.get("method") == "initialize":
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": {}}) + "\\n")
            sys.stdout.flush()
        elif req.get("method") == "tools/list":
            resp_data = {"jsonrpc": "2.0", "id": req["id"], "result": {"tools": [{"name": "fake_tool"}]}}
            sys.stdout.write(json.dumps(resp_data) + "\\n")
            sys.stdout.flush()
            sys.stdout.flush()
    except Exception:
        pass
""")
    import sys
    return {"name": "mocked", "command": sys.executable, "args": [str(script)]}

def test_mcp_discover(mocked_mcp_server):
    tools = MCPManager.discover(mocked_mcp_server)
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "mocked__fake_tool"

def test_mcp_call(mocked_mcp_server):
    res = MCPManager.call_tool(mocked_mcp_server, "mocked__fake_tool", {"arg": "val"})
    assert "hello" in res
