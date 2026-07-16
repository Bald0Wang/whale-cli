"""A minimal real MCP stdio server for trying Whale CLI's MCP client."""
from mcp.server.fastmcp import FastMCP


server = FastMCP("whale-cli-echo")


@server.tool()
def echo(text: str) -> str:
    """Return text so clients can verify MCP discovery and tools/call."""
    return f"echo:{text}"


if __name__ == "__main__":
    server.run(transport="stdio")
