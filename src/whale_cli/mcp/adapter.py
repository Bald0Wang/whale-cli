"""Adapt remote MCP tools to Whale CLI's local Tool contract."""
from __future__ import annotations

from typing import Any

from ..tools.base import Tool, err, ok
from .models import MCPRemoteTool


class MCPToolAdapter(Tool):
    def __init__(self, *, server_name: str, remote_tool: MCPRemoteTool, client: Any):
        self._client = client
        self._remote_name = remote_tool.name
        self.name = f"mcp__{_safe_name(server_name)}__{_safe_name(remote_tool.name)}"
        self.description = remote_tool.description or f"Remote MCP tool {remote_tool.name} from {server_name}."
        self.approval_action = f"call MCP tool ({server_name})"
        self.schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": remote_tool.input_schema or {"type": "object", "properties": {}},
            },
        }

    def __call__(self, **kwargs: Any) -> dict:
        try:
            result = self._client.call_tool(self._remote_name, kwargs)
        except TimeoutError:
            return err("MCP call timed out", exit_code=124)
        except Exception as exc:
            return err(f"MCP call failed: {exc}")
        if result.is_error:
            return err(result.text or "MCP tool returned an error")
        return ok(result.text)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
