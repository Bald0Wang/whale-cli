"""Typed data kept independent from a concrete MCP SDK session.

MCPServerConfig now describes all three transports (stdio / http / sse) so the
loader and client can route on `transport` without transport-specific dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

VALID_TRANSPORTS = ("stdio", "http", "sse")


@dataclass(frozen=True)
class MCPServerConfig:
    """One MCP server connection.

    Fields are grouped by transport; only the relevant subset is required:

    - stdio:  ``command`` (required), ``args``, ``env``
    - http:   ``url`` (required), ``headers``, ``auth``
    - sse:    ``url`` (required), ``headers``, ``auth``
    """

    name: str
    transport: str  # one of VALID_TRANSPORTS
    # stdio fields
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    # http / sse fields
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    # auth: "" (none) | "oauth" | a bare API-key string consumed by the client
    auth: str = ""
    # shared
    timeout_s: float = 30.0

    def __post_init__(self) -> None:
        if self.transport not in VALID_TRANSPORTS:
            raise ValueError(
                f"unsupported MCP transport {self.transport!r}; must be one of {VALID_TRANSPORTS}"
            )
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"MCP server {self.name!r}: stdio transport requires 'command'")
        if self.transport in ("http", "sse") and not self.url:
            raise ValueError(f"MCP server {self.name!r}: {self.transport} transport requires 'url'")


@dataclass(frozen=True)
class MCPRemoteTool:
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass(frozen=True)
class MCPCallResult:
    text: str
    is_error: bool = False
    structured_content: Any = None
