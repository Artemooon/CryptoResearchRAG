import sys
import json
from contextlib import AsyncExitStack
from os import path
from pathlib import Path
from typing import Any, Awaitable, Callable, ClassVar, Self
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


class McpClient:
    client_session: ClassVar[ClientSession]

    def __init__(self, server_path: str, transport: str | None = None):
        self.server_path = server_path
        self.transport = transport or self._infer_transport(server_path)
        self.repo_root = Path(__file__).resolve().parent.parent
        self.exit_stack = AsyncExitStack()

    @staticmethod
    def _infer_transport(server_path: str) -> str:
        parsed = urlparse(server_path)
        if parsed.scheme in {"http", "https"}:
            return "sse" if parsed.path.rstrip("/").endswith("/sse") else "streamable-http"
        return "stdio"

    async def __aenter__(self) -> Self:
        cls = type(self)
        cls.client_session = await self._connect_to_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.exit_stack.aclose()

    async def _connect_to_server(self) -> ClientSession:
        try:
            if self.transport == "stdio":
                read, write = await self._connect_stdio()
            elif self.transport in {"streamable-http", "sse"}:
                read, write = await self._connect_http()
            else:
                raise ValueError(f"Unsupported MCP transport: {self.transport}")

            client_session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await client_session.initialize()
            return client_session
        except Exception as exc:
            raise RuntimeError("Error: Failed to connect to server") from exc

    async def _connect_stdio(self):
        if self.server_path.endswith(".py") and path.exists(self.server_path):
            server_command = sys.executable
            server_args = [self.server_path]
        else:
            server_command = sys.executable
            server_args = ["-m", self.server_path]

        print("server path", f"{server_command} {' '.join(server_args)}")
        return await self.exit_stack.enter_async_context(
            stdio_client(
                server=StdioServerParameters(
                    command=server_command,
                    args=server_args,
                    cwd=str(self.repo_root),
                    env=None,
                )
            )
        )

    async def _connect_http(self):
        if self.transport == "streamable-http":
            read, write, _get_session_id = await self.exit_stack.enter_async_context(
                streamable_http_client(self.server_path)
            )
            return read, write

        return await self.exit_stack.enter_async_context(sse_client(self.server_path))

    async def list_all_members(self) -> None:
        """List all available tools, prompts, and resources."""
        print("MCP Server Members")
        print("=" * 50)

        sections = {
            "tools": self.client_session.list_tools,
            "prompts": self.client_session.list_prompts,
            "resources": self.client_session.list_resources,
        }
        for section, listing_method in sections.items():
            await self._list_section(section, listing_method)

        print("\n" + "=" * 50)

    async def print_prompt(self, name: str, arguments: dict[str, str]) -> None:
        """Fetch and print an MCP prompt."""
        result = await self.client_session.get_prompt(name, arguments=arguments)
        description = getattr(result, "description", None)
        if description:
            print(description)
            print("=" * len(description))

        for message in result.messages:
            role = getattr(message, "role", "unknown")
            content = getattr(message, "content", None)
            content_type = getattr(content, "type", None)
            if content_type == "text":
                print(f"{role}> {content.text}")
            elif content is not None:
                print(f"{role}> {json.dumps(content.model_dump(), default=str)}")
            else:
                print(f"{role}> {json.dumps(message.model_dump(), default=str)}")

    async def _list_section(
        self,
        section: str,
        list_method: Callable[[], Awaitable[Any]],
    ) -> None:
        try:
            items = getattr(await list_method(), section)
            if items:
                print(f"\n{section.upper()} ({len(items)}):")
                print("-" * 30)
                for item in items:
                    description = item.description or "No description"
                    print(f" > {item.name} - {description}")
            else:
                print(f"\n{section.upper()}: None available")
        except Exception as exc:
            print(f"\n{section.upper()}: Error - {exc}")
