from __future__ import annotations

import json
import sys
from pathlib import Path

from whale_cli.mcp import (
    MCPCallResult,
    MCPRemoteTool,
    load_mcp_server_configs,
    load_mcp_tools,
    load_mcp_tools_with_lifecycle,
)
from whale_cli.soul.approval import Approval
from whale_cli.soul.soul import Soul
from whale_cli.soul.toolset import Toolset

from .conftest import make_tool_call


class _FakeMCPClient:
    def __init__(self, config):
        self.config = config
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def list_tools(self):
        return [
            MCPRemoteTool(
                name="echo",
                description="Echo text from a remote server.",
                input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            )
        ]

    def start(self):
        return self.list_tools()

    def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        if arguments.get("text") == "fail":
            return MCPCallResult(text="remote failure", is_error=True)
        return MCPCallResult(text=f"remote:{arguments['text']}")

    def close(self):
        self.closed = True


class _FailingMCPClient(_FakeMCPClient):
    def start(self):
        raise RuntimeError("server is unavailable")


def _write_config(path: Path, *, command: str = "fake-server", args: list[str] | None = None) -> Path:
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "echo-server",
                        "transport": "stdio",
                        "command": command,
                        "args": args or [],
                        "timeout_s": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_mcp_loader_adapts_remote_schema_and_normalizes_results(tmp_path):
    config_path = _write_config(tmp_path / "mcp.json")
    created: list[_FakeMCPClient] = []

    def _factory(config):
        client = _FakeMCPClient(config)
        created.append(client)
        return client

    tools = load_mcp_tools(config_path, client_factory=_factory)

    assert [tool.name for tool in tools] == ["mcp__echo_server__echo"]
    assert tools[0].schema["function"]["parameters"]["required"] == ["text"]
    assert tools[0].approval_action == "call MCP tool (echo-server)"
    assert tools[0](text="hello")["stdout"] == "remote:hello"
    assert tools[0](text="fail")["exit_code"] == 1
    assert created[0].calls == [("echo", {"text": "hello"}), ("echo", {"text": "fail"})]


def test_mcp_loader_accepts_claude_desktop_style_http_config(tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "remote-api": {
                        "transport": "http",
                        "url": "https://mcp.example.test/mcp",
                        "headers": {"X-Api-Key": "test-key"},
                        "timeout_s": 12,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    [config] = load_mcp_server_configs(config_path)

    assert config.name == "remote-api"
    assert config.transport == "http"
    assert config.url == "https://mcp.example.test/mcp"
    assert config.headers == {"X-Api-Key": "test-key"}
    assert config.timeout_s == 12


def test_mcp_loader_accepts_modelscope_sse_type_config(tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "amap-maps": {
                        "type": "sse",
                        "url": "https://mcp.api-inference.modelscope.net/962fac0b1d6543/sse",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    [config] = load_mcp_server_configs(config_path)

    assert config.name == "amap-maps"
    assert config.transport == "sse"
    assert config.url.endswith("/sse")


def test_mcp_lifecycle_closes_all_clients(tmp_path):
    config_path = _write_config(tmp_path / "mcp.json")
    created: list[_FakeMCPClient] = []

    def _factory(config):
        client = _FakeMCPClient(config)
        created.append(client)
        return client

    lifecycle, tools = load_mcp_tools_with_lifecycle(config_path, client_factory=_factory)

    assert [tool.name for tool in tools] == ["mcp__echo_server__echo"]
    lifecycle.close()
    assert created[0].closed is True
    assert lifecycle.clients == []


def test_mcp_loader_closes_a_client_when_discovery_fails(tmp_path):
    config_path = _write_config(tmp_path / "mcp.json")
    created: list[_FailingMCPClient] = []

    def _factory(config):
        client = _FailingMCPClient(config)
        created.append(client)
        return client

    lifecycle, tools = load_mcp_tools_with_lifecycle(config_path, client_factory=_factory)

    assert tools == []
    assert lifecycle.clients == []
    assert created[0].closed is True


def test_mcp_stdio_server_is_discovered_and_called(tmp_path):
    server_path = Path(__file__).parents[1] / "examples" / "mcp_echo_server.py"
    config_path = _write_config(
        tmp_path / "mcp.json",
        command=sys.executable,
        args=[str(server_path)],
    )

    tools = load_mcp_tools(config_path)

    assert [tool.name for tool in tools] == ["mcp__echo_server__echo"]
    result = tools[0](text="hello")
    assert result == {
        "stdout": "echo:hello",
        "stderr": "",
        "exit_code": 0,
        "changed_files": [],
    }


def test_mcp_tools_join_the_default_soul_toolset(tmp_path, monkeypatch, mock_llm):
    server_path = Path(__file__).parents[1] / "examples" / "mcp_echo_server.py"
    config_path = _write_config(
        tmp_path / "mcp.json",
        command=sys.executable,
        args=[str(server_path)],
    )
    monkeypatch.setenv("WHALE_MCP_CONFIG", str(config_path))

    soul = Soul(llm=mock_llm(["ok"]), approval=Approval(yolo=True))

    assert "mcp__echo_server__echo" in soul.toolset.names
    soul.close()
    assert soul._mcp_lifecycle.clients == []


def test_soul_round_trip_calls_real_mcp_stdio(tmp_path, monkeypatch, mock_llm):
    server_path = Path(__file__).parents[1] / "examples" / "mcp_echo_server.py"
    config_path = _write_config(
        tmp_path / "mcp.json",
        command=sys.executable,
        args=[str(server_path)],
    )
    monkeypatch.setenv("WHALE_MCP_CONFIG", str(config_path))
    llm = mock_llm(
        [
            [make_tool_call("mcp_1", "mcp__echo_server__echo", {"text": "agent-round-trip"})],
            "The MCP server returned echo:agent-round-trip.",
        ]
    )
    soul = Soul(llm=llm, approval=Approval(yolo=True))
    assert "mcp__echo_server__echo" in soul.toolset.names

    outcome = soul.run("Call the configured MCP echo tool.")

    tool_message = next(message for message in soul.messages if message["role"] == "tool")
    assert "echo:agent-round-trip" in tool_message["content"]
    assert outcome.summary == "The MCP server returned echo:agent-round-trip."
    soul.close()


def test_mcp_tool_uses_the_standard_approval_gate(tmp_path):
    config_path = _write_config(tmp_path / "mcp.json")
    created: list[_FakeMCPClient] = []

    def _factory(config):
        client = _FakeMCPClient(config)
        created.append(client)
        return client

    tool = load_mcp_tools(config_path, client_factory=_factory)[0]
    toolset = Toolset([tool])
    toolset.set_approver(lambda action, description: False)

    result = toolset.handle(tool.name, '{"text": "hello"}')

    assert result["exit_code"] == 126
    assert created[0].calls == []
