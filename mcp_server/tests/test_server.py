import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = str(Path(__file__).resolve().parents[1] / "main.py")
EXPECTED_TOOLS = [
    "search_coingecko_tokens",
    "resolve_portfolio_id_from_name",
    "get_portfolio_stats",
    "add_entry_to_portfolio",
]


@pytest.mark.asyncio
async def test_mcp_server_connection():
    """Connect to an MCP server and verify the tools."""

    exit_stack = AsyncExitStack()
    server_params = StdioServerParameters(command="python", args=[SERVER_PATH], env=None)

    stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio, write = stdio_transport
    session = await exit_stack.enter_async_context(ClientSession(stdio, write))

    await session.initialize()

    response = await session.list_tools()
    tools = response.tools
    tool_names = [tool.name for tool in tools]
    tool_descriptions = [tool.description for tool in tools]

    print("\nYour server has the following tools:")
    for tool_name, tool_description in zip(tool_names, tool_descriptions):
        print(f"{tool_name}: {tool_description}")

    assert sorted(EXPECTED_TOOLS) == sorted(tool_names)

    await exit_stack.aclose()
