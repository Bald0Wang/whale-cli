"""Synchronous facade over a reusable ``fastmcp.Client`` configuration.

Design (aligned with kimi-cli's KimiToolset MCP handling):

- One :class:`fastmcp.Client` per server, created in ``__init__`` and held for
  the life of this :class:`MCPClient`. The fastmcp ``Client`` is a *reentrant*
  factory: ``async with client`` opens a transport session (stdio subprocess /
  HTTP connection), and exiting closes it. Whale CLI re-enters it for discovery
  and each call, which keeps the synchronous teaching implementation simple.
- :meth:`start` connects + initializes + lists tools once (discovery).
- :meth:`call_tool` re-enters ``async with client`` for each call.
- :meth:`close` releases the reusable client and transport configuration.

Synchronous bridge: Whale CLI's ``Soul.run`` is synchronous, so each async
operation is run via :func:`_run_sync` (a fresh ``asyncio.run`` per call). The
``fastmcp.Client`` object itself is a plain object that survives across these
one-shot loops — it does not bind to any single event loop.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, TypeVar

from .models import MCPCallResult, MCPRemoteTool, MCPServerConfig

T = TypeVar("T")


class MCPClient:
    """Discover and call tools from one MCP server (stdio / http / sse)."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._client = self._build_client()
        self._connected = False

    # -- transport construction -------------------------------------------

    def _build_client(self):
        """Construct the reusable ``fastmcp.Client`` for this config."""
        from fastmcp import Client
        from fastmcp.client.transports import SSETransport, StdioTransport, StreamableHttpTransport

        cfg = self.config
        if cfg.transport == "stdio":
            transport: Any = StdioTransport(command=cfg.command, args=list(cfg.args), env=dict(cfg.env) or None)
            return Client(transport, timeout=cfg.timeout_s)

        # http / sse share the url + headers + auth shape.
        headers = dict(cfg.headers)
        auth = self._resolve_auth()
        if cfg.transport == "sse":
            transport = SSETransport(url=cfg.url, headers=headers or None, auth=auth)
        else:  # http / streamable-http
            transport = StreamableHttpTransport(url=cfg.url, headers=headers or None, auth=auth)
        return Client(transport, timeout=cfg.timeout_s)

    def _resolve_auth(self) -> Any:
        """Turn the config ``auth`` field into a fastmcp/httpx auth value.

        - ``""``      → None (no auth; rely on headers for API keys)
        - ``"oauth"`` → an OAuthClientProvider built via :mod:`whale_cli.mcp.auth`
                        (only assembled when actually used, to keep import light)
        - any other string → treated as a bearer API key
        """
        cfg = self.config
        if not cfg.auth:
            return None
        if cfg.auth == "oauth":
            from .auth import create_oauth_provider

            return create_oauth_provider(cfg.url)
        # Bare API-key string: fastmcp/httpx accepts a str as a bearer token.
        return cfg.auth

    # -- lifecycle --------------------------------------------------------

    def start(self) -> list[MCPRemoteTool]:
        """Connect, initialize, and discover tools. Called once at load time."""
        tools = _run_sync(self._list_tools())
        self._connected = True
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPCallResult:
        """Call a remote tool. Re-enters the reusable client each call."""
        if not self._connected:
            # Allow call without explicit start() (auto-connect); rare path.
            self._connected = True
        return _run_sync(self._call_tool(name, arguments))

    def close(self) -> None:
        """Release the persistent client. Safe to call more than once."""
        if self._client is None:
            return
        try:
            _run_sync(self._client.close())
        except Exception as exc:
            # Best-effort: never raise from close.
            print(f"[MCP] Error closing {self.config.name!r}: {exc}")
        finally:
            self._client = None
            self._connected = False

    # -- async internals --------------------------------------------------

    async def _list_tools(self) -> list[MCPRemoteTool]:
        async with self._client:
            response = await self._client.list_tools()
            return [_to_remote_tool(tool) for tool in response]

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> MCPCallResult:
        async with self._client:
            result = await self._client.call_tool(name, arguments=arguments, raise_on_error=False)
        return _to_call_result(result)


# Backward-compat alias: older code imported MCPStdioClient. It now routes
# through the unified MCPClient but only accepts stdio configs (matching the
# original contract).
class MCPStdioClient(MCPClient):
    def __init__(self, config: MCPServerConfig):
        if config.transport != "stdio":
            raise ValueError(f"MCPStdioClient only supports stdio, got {config.transport!r}")
        super().__init__(config)


# -- helpers ---------------------------------------------------------------


def _to_remote_tool(tool: Any) -> MCPRemoteTool:
    schema = getattr(tool, "inputSchema", getattr(tool, "input_schema", {})) or {}
    schema = _as_dict(schema)
    return MCPRemoteTool(
        name=str(tool.name),
        description=str(getattr(tool, "description", "") or ""),
        input_schema=schema,
    )


def _to_call_result(result: Any) -> MCPCallResult:
    content = getattr(result, "content", []) or []
    text_parts = [_content_to_text(c) for c in content]
    structured = getattr(result, "structuredContent", getattr(result, "structured_content", None))
    if structured is not None and not any(text_parts):
        text_parts.append(json.dumps(_as_jsonable(structured), ensure_ascii=False))
    is_error = bool(getattr(result, "isError", getattr(result, "is_error", False)))
    return MCPCallResult(
        text="\n".join(p for p in text_parts if p),
        is_error=is_error,
        structured_content=structured,
    )


def _run_sync(coro: Awaitable[T]) -> T:
    """Run a coroutine from synchronous code.

    Mirrors the original MCPStdioClient behavior: a fresh event loop per call.
    fastmcp.Client objects are plain objects and survive across these loops.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("MCP calls cannot run inside an existing asyncio event loop")


def _content_to_text(content: Any) -> str:
    text = getattr(content, "text", None)
    if text is not None:
        return str(text)
    return json.dumps(_as_jsonable(content), ensure_ascii=False)


def _as_dict(value: Any) -> dict[str, Any]:
    dumped = _as_jsonable(value)
    return dumped if isinstance(dumped, dict) else {"type": "object", "properties": {}}


def _as_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if hasattr(value, "dict"):
        return value.dict()
    return value
