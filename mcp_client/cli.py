import argparse

def parse_args():
    """Parse command line arguments and return parsed args."""
    parser = argparse.ArgumentParser(description="A minimal MCP client")
    parser.add_argument(
        "server_path",
        type=str,
        help=(
            "module/file path for stdio, or HTTP MCP URL, for example "
            "'mcp_server.main', 'mcp_server/main.py', or 'http://127.0.0.1:8000/mcp'"
        ),
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=None,
        help="transport to use. Defaults to stdio for paths and streamable-http for HTTP URLs.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--members",
        action="store_true",
        help="list the MCP server's tools, prompts, and resources",
    )
    group.add_argument(
        "--chat",
        action="store_true",
        help="start an AI-powered chat with MCP server integration (requires OPENAI_API_KEY)",
    )
    group.add_argument(
        "--prompt",
        metavar="NAME",
        help="fetch and print an MCP prompt by name",
    )
    parser.add_argument(
        "--prompt-arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="argument for --prompt. May be repeated.",
    )
    return parser.parse_args()
