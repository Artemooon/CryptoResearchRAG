from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
from contextlib import asynccontextmanager
from getpass import getpass
from typing import Any, Awaitable, TypeVar

from dotenv import load_dotenv

import requests

from mcp_client.client import McpClient
from platform_config import get_platform_auth_token


load_dotenv()

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-5.5"
SPINNER_FRAMES = ("|", "/", "-", "\\")
T = TypeVar("T")


def _tool_to_openai_function(tool: Any) -> dict[str, Any]:
    parameters = copy.deepcopy(tool.inputSchema)
    properties = parameters.get("properties", {})
    if "auth_token" in properties:
        properties.pop("auth_token", None)
        parameters["properties"] = properties

        required = parameters.get("required", [])
        parameters["required"] = [field for field in required if field != "auth_token"]

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": parameters,
        },
    }


def _tool_result_to_text(result: Any) -> str:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return json.dumps(structured, indent=2, sort_keys=True, default=str)

    pieces: list[str] = []
    for content in getattr(result, "content", []) or []:
        content_type = getattr(content, "type", None)
        if content_type == "text":
            pieces.append(getattr(content, "text", ""))
        else:
            pieces.append(json.dumps(content.model_dump(), default=str))

    return "\n".join(piece for piece in pieces if piece) or "{}"


def _redact_tool_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(arguments)
    if "auth_token" in redacted:
        redacted["auth_token"] = "<redacted>"
    return redacted


def _call_openai(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    response = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        },
        timeout=90,
    )
    response.raise_for_status()
    return response.json()


async def _spinner(label: str) -> None:
    index = 0
    while True:
        frame = SPINNER_FRAMES[index % len(SPINNER_FRAMES)]
        print(f"\r{frame} {label}", end="", flush=True)
        index += 1
        await asyncio.sleep(0.12)


@asynccontextmanager
async def _loader(label: str):
    if not sys.stdout.isatty():
        yield
        return

    task = asyncio.create_task(_spinner(label))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        print("\r" + " " * (len(label) + 4) + "\r", end="", flush=True)


async def _with_loader(label: str, awaitable: Awaitable[T]) -> T:
    async with _loader(label):
        return await awaitable


async def run_chat(server_path: str, transport: str | None = None) -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --chat")

    platform_auth_token = get_platform_auth_token()
    if not platform_auth_token and sys.stdin.isatty():
        platform_auth_token = getpass("Platform auth token (hidden, leave empty to skip): ").strip() or None

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    debug_tools = os.environ.get("MCP_DEBUG_TOOLS") == "1"
    system_prompt = (
        "You are a portfolio assistant that can use MCP tools. "
        "When the user asks to create or change a portfolio entry, "
        "call the available MCP tool with the exact fields required. "
        "Users may provide portfolio names instead of portfolio IDs; use "
        "portfolio_name directly or resolve it with the portfolio lookup tool. "
        "Do not ask users for raw portfolio IDs unless name resolution fails. "
        "The host injects the platform auth token locally; do not ask "
        "the user to reveal it in the chat. If a write request is missing "
        "other required fields, ask a follow-up question before calling "
        "the tool. After a successful tool call, summarize the result "
        "briefly and clearly."
    )

    async with McpClient(server_path, transport=transport) as client:
        tools_response = await client.client_session.list_tools()
        auth_tool_names = {
            tool.name
            for tool in tools_response.tools
            if "auth_token" in tool.inputSchema.get("properties", {})
        }
        tools = [_tool_to_openai_function(tool) for tool in tools_response.tools]

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

        while True:
            user_input = input("You> ").strip()
            if user_input.lower() in {"/exit", "/quit"}:
                return
            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})

            while True:
                response = await _with_loader(
                    "Thinking...",
                    asyncio.to_thread(
                        _call_openai,
                        api_key=api_key,
                        model=model,
                        messages=messages,
                        tools=tools,
                    ),
                )
                assistant_message = response["choices"][0]["message"]
                assistant_history_message: dict[str, Any] = {"role": "assistant"}
                if assistant_message.get("content") is not None:
                    assistant_history_message["content"] = assistant_message.get("content")
                if assistant_message.get("tool_calls"):
                    assistant_history_message["tool_calls"] = assistant_message["tool_calls"]
                messages.append(assistant_history_message)

                content = assistant_message.get("content")
                if content:
                    print(f"Assistant> {content}")

                tool_calls = assistant_message.get("tool_calls") or []
                if not tool_calls:
                    break

                for tool_call in tool_calls:
                    function = tool_call["function"]
                    tool_name = function["name"]
                    arguments = json.loads(function.get("arguments") or "{}")
                    if tool_name in auth_tool_names and platform_auth_token:
                        arguments["auth_token"] = platform_auth_token
                    if debug_tools:
                        print(
                            "Debug tool call>",
                            tool_name,
                            json.dumps(
                                _redact_tool_arguments(arguments),
                                default=str,
                                sort_keys=True,
                            ),
                        )
                    tool_result = await _with_loader(
                        f"Running {tool_name}...",
                        client.client_session.call_tool(
                            tool_name,
                            arguments=arguments,
                        ),
                    )
                    tool_text = _tool_result_to_text(tool_result)
                    if debug_tools:
                        print(f"Debug tool result> {tool_text}")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_text,
                        }
                    )
