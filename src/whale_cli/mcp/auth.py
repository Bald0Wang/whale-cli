"""OAuth scaffolding for MCP clients.

This module provides the *plumbing* for OAuth so a server declared with
``"auth": "oauth"`` can be wired up. It is deliberately minimal:

- :class:`FileTokenStorage` persists tokens + client registration to disk
  (``~/.whale/mcp-oauth/<server>/``), so re-connecting does not re-authorize.
- :func:`create_oauth_provider` assembles an :class:`OAuthClientProvider`
  (which is an ``httpx.Auth``) ready to pass to a fastmcp transport.

The interactive browser flow (``redirect_handler`` / ``callback_handler``) is
**not** implemented here: when authorization is required, we print the URL and
instruct the user to complete it manually. A future revision can add a local
callback HTTP server. For API-key auth (the common case), just put the key in
the server's ``headers`` and leave ``auth`` empty — no OAuth needed.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from .models import MCPServerConfig


def _safe_dir_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name) or "server"


def _storage_dir(server_url: str) -> Path:
    base = Path.home() / ".whale" / "mcp-oauth" / _safe_dir_name(server_url)
    base.mkdir(parents=True, exist_ok=True)
    return base


class FileTokenStorage:
    """Minimal :class:`TokenStorage` implementation backed by JSON files.

    Tokens live at ``~/.whale/mcp-oauth/<server>/tokens.json`` and client
    registration info at ``.../client.json``. This keeps re-authorization
    out of the common path while staying fully transparent (no keyring dep).
    """

    def __init__(self, server_url: str):
        self._dir = _storage_dir(server_url)

    async def get_tokens(self) -> Any:
        path = self._dir / "tokens.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def set_tokens(self, tokens: Any) -> None:
        (self._dir / "tokens.json").write_text(json.dumps(tokens, ensure_ascii=False, default=str), encoding="utf-8")

    async def get_client_info(self) -> Any:
        path = self._dir / "client.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def set_client_info(self, client_info: Any) -> None:
        (self._dir / "client.json").write_text(
            json.dumps(client_info, ensure_ascii=False, default=str), encoding="utf-8"
        )


async def _print_redirect_handler(authorization_url: str) -> None:
    """Default redirect handler: show the URL for manual authorization.

    A real implementation would ``webbrowser.open(authorization_url)`` and run
    a local callback server. For now we keep it non-blocking-safe by printing.
    """
    print(f"[MCP OAuth] Open this URL to authorize:\n  {authorization_url}")
    print("[MCP OAuth] Complete authorization in your browser, then restart the CLI.")


async def _pending_callback_handler() -> tuple[str, str | None]:
    """Default callback handler: not implemented.

    Returns ``(code, state)`` from the OAuth redirect. Without a local server
    we cannot capture it, so we raise to make the gap explicit rather than
    hanging forever.
    """
    raise NotImplementedError(
        "Interactive OAuth callback capture is not implemented. "
        "Use API-key auth via 'headers' instead, or supply your own callback handler."
    )


def create_oauth_provider(server_url: str) -> Any:
    """Build an :class:`OAuthClientProvider` for ``server_url``.

    Returns the provider (an ``httpx.Auth`` subclass) ready to pass as the
    ``auth=`` argument of a fastmcp transport. Token persistence is handled by
    :class:`FileTokenStorage`. The interactive flow is stubbed (see module
    docstring).
    """
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

    client_metadata = OAuthClientMetadata(
        client_name="whale-cli",
        redirect_uris=["http://localhost:0/callback"],
        grant_types=["authorization_code", "refresh_token"],
        token_endpoint_auth_method="none",
        scope="mcp",
    )
    storage = FileTokenStorage(server_url)
    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=client_metadata,
        storage=storage,
        redirect_handler=_print_redirect_handler,
        callback_handler=_pending_callback_handler,
    )
