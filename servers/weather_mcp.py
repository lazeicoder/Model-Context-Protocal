from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="weather")

@mcp.tool()
async def get_weather(location: str) -> str:
    return f"The weather in {location} is sunny."



if __name__ == "__main__":
    mcp.run(transport="stdio")