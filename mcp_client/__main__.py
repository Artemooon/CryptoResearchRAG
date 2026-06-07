import asyncio

from mcp_client.cli import parse_args
from mcp_client.chat import run_chat
from mcp_client.client import McpClient


def _parse_prompt_args(raw_args: list[str]) -> dict[str, str]:
    prompt_args: dict[str, str] = {}
    for raw_arg in raw_args:
        if "=" not in raw_arg:
            raise RuntimeError(f"Invalid --prompt-arg {raw_arg!r}; expected KEY=VALUE")
        key, value = raw_arg.split("=", 1)
        if not key:
            raise RuntimeError(f"Invalid --prompt-arg {raw_arg!r}; key must not be empty")
        prompt_args[key] = value
    return prompt_args


async def main() -> None:
    """Run the MCP client with the specified options."""
    args = parse_args()

    try:
        if args.chat:
            await run_chat(args.server_path, transport=args.transport)
        else:
            async with McpClient(args.server_path, transport=args.transport) as client:
                if args.prompt:
                    await client.print_prompt(args.prompt, _parse_prompt_args(args.prompt_arg))
                else:
                    await client.list_all_members()
    except RuntimeError as exc:
        print(exc)


if __name__ == "__main__":
    asyncio.run(main())
