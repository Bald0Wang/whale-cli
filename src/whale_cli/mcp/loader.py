"""Load MCP servers from a project-local JSON configuration file.

Supports the Claude Desktop ``mcpServers`` format and a legacy ``servers``
array format (auto-converted). Each adapter retains one reusable
``fastmcp.Client`` configuration per server; see
:class:`whale_cli.mcp.client.MCPClient` and :class:`MCPLifecycle`.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

from ..tools.base import Tool
from .adapter import MCPToolAdapter
from .client import MCPClient
from .models import MCPServerConfig

ClientFactory = Callable[[MCPServerConfig], MCPClient]


def default_mcp_config_path() -> Path:
    configured = os.environ.get("WHALE_MCP_CONFIG")
    if configured:
        return Path(configured).expanduser()
    return Path(os.getcwd()) / ".whale_cli" / "mcp.json"


def load_mcp_tools(
    config_path: str | Path | None = None,
    *,
    client_factory: ClientFactory = MCPClient,
) -> List[Tool]:
    """Best-effort discovery so a broken remote server does not block the CLI.

    Each server is connected once (start + initialize + list_tools) here, and
    the resulting reusable client is held by every adapter it produced. The
    caller is responsible for closing them via :class:`MCPLifecycle` — see
    :func:`load_mcp_tools_with_lifecycle` for the pair that returns both.
    """
    lifecycle, tools = load_mcp_tools_with_lifecycle(config_path, client_factory=client_factory)
    # Without a lifecycle owner the clients are leaked; callers that care about
    # cleanup should use load_mcp_tools_with_lifecycle directly.
    return tools


def load_mcp_tools_with_lifecycle(
    config_path: str | Path | None = None,
    *,
    client_factory: ClientFactory = MCPClient,
) -> tuple["MCPLifecycle", List[Tool]]:
    """Like :func:`load_mcp_tools` but also returns the lifecycle handle.

    Use this when you can close the clients on shutdown (e.g. the REPL). The
    returned ``MCPLifecycle`` holds every successfully started client so their
    transport resources can be released
    can be closed in one call.
    """
    try:
        configs = load_mcp_server_configs(config_path)
    except Exception as exc:
        print(f"[MCP] Config skipped: {exc}")
        return MCPLifecycle([]), []

    tools: List[Tool] = []
    clients: List[MCPClient] = []
    for config in configs:
        client: MCPClient | None = None
        try:
            client = client_factory(config)
            remote_tools = client.start()
            clients.append(client)
            tools.extend(
                MCPToolAdapter(server_name=config.name, remote_tool=remote, client=client)
                for remote in remote_tools
            )
        except Exception as exc:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass
            print(f"[MCP] Server {config.name!r} skipped: {exc}")
    return MCPLifecycle(clients), tools


def load_mcp_server_configs(config_path: str | Path | None = None) -> list[MCPServerConfig]:
    path = Path(config_path) if config_path is not None else default_mcp_config_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mcp config must be a JSON object")

    # Preferred: Claude Desktop mcpServers map.
    servers = data.get("mcpServers")
    if isinstance(servers, dict):
        return [_parse_server(name, item) for name, item in servers.items()]

    # Legacy: {"servers": [ {name, transport, ...}, ... ]}
    legacy = data.get("servers")
    if isinstance(legacy, list):
        configs = []
        for item in legacy:
            if not isinstance(item, dict):
                raise ValueError("each MCP server must be an object")
            configs.append(_parse_server(str(item.get("name") or ""), item))
        return configs

    raise ValueError("mcp config must contain a 'mcpServers' object or a 'servers' array")


def _parse_server(name: str, item: object) -> MCPServerConfig:
    if not isinstance(item, dict):
        raise ValueError(f"MCP server {name!r} must be an object")

    # Name comes from the mcpServers key; allow an inline "name" fallback.
    name = (name or str(item.get("name") or "")).strip()
    if not name:
        raise ValueError("each MCP server needs a name")

    # ``transport`` is Whale CLI's explicit name; ``type`` is used by several
    # MCP config producers (including ModelScope's SSE examples).
    transport = str(item.get("transport") or item.get("type") or "").strip()

    # Infer transport from fields only when neither explicit spelling is set.
    if not transport:
        if item.get("url"):
            transport = "http"
        elif item.get("command"):
            transport = "stdio"

    args = item.get("args") or []
    env = item.get("env") or {}
    headers = item.get("headers") or {}
    auth = str(item.get("auth") or "").strip()

    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ValueError(f"MCP server {name!r}: args must be a string array")
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError(f"MCP server {name!r}: env must be a string map")
    if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
        raise ValueError(f"MCP server {name!r}: headers must be a string map")

    timeout_s = float(item.get("timeout_s", 30))
    if timeout_s <= 0:
        raise ValueError(f"MCP server {name!r}: timeout_s must be > 0")

    return MCPServerConfig(
        name=name,
        transport=transport,
        command=str(item.get("command") or "").strip(),
        args=list(args),
        env={str(k): str(v) for k, v in env.items()},
        url=str(item.get("url") or "").strip(),
        headers={str(k): str(v) for k, v in headers.items()},
        auth=auth,
        timeout_s=timeout_s,
    )


@dataclass
class MCPLifecycle:
    """Owns the MCP clients created during tool loading.

    Call :meth:`close` once on shutdown (e.g. when the REPL exits) to release
    every connection. Closing is best-effort — a failing close is logged and
    does not stop the others.
    """

    clients: List[MCPClient] = field(default_factory=list)

    def close(self) -> None:
        for client in self.clients:
            try:
                client.close()
            except Exception as exc:  # best-effort; never crash shutdown
                print(f"[MCP] Error closing client: {exc}")
        self.clients.clear()
