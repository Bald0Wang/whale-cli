from mcp.server.fastmcp import FastMCP


server = FastMCP("whale-cli-test-echo")


@server.tool()
def echo(text: str) -> str:
    return f"echo:{text}"


if __name__ == "__main__":
    server.run(transport="stdio")
