# CryptoResearchRAG MCP

This project contains a small MCP server and client.

The server exposes portfolio tools plus token lookup and RAG search utilities. The client can connect through local `stdio`, Streamable HTTP, or legacy SSE.

## Requirements

- Python 3.13+
- Project dependencies installed from `pyproject.toml`

If you use `uv`, install/sync dependencies with:

```bash
uv sync
```

## Start Postgres

The project includes a Docker Compose Postgres service with pgvector enabled. Start it with:

```bash
docker compose up -d postgres
```

On first database creation, Docker automatically runs:

```text
schema.sql
```

through the Postgres init directory:

```text
/docker-entrypoint-initdb.d/001-schema.sql
```

The default connection URL is:

```bash
export RAG_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/cryptoresearchrag"
```

You can override defaults in `.env`:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=cryptoresearchrag
POSTGRES_PORT=5432
RAG_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cryptoresearchrag
```

Postgres init scripts run only when the Docker volume is first created. If the database volume already exists and you change `schema.sql`, apply the schema through `db.init_db()` or recreate the volume intentionally.

## Ingest And Search Crypto School Data

`search.py` searches the Postgres `document_chunks` table. It does not read `crypto-school-data.jsonl` directly at query time.

Before searching, ingest the JSONL data into Postgres:

```bash
python embeddings.py
```

If `crypto-school-data.jsonl` is missing, `embeddings.py` automatically runs `data-extractor.py` first.

To generate only the JSONL file:

```bash
python data-extractor.py
```

Or pass an explicit JSONL path:

```bash
python embeddings.py --input /path/to/crypto-school-data.jsonl
```

To disable automatic generation and fail when the JSONL file is missing:

```bash
python embeddings.py --no-generate
```

Then run search:

```bash
python search.py
```

RAG answer generation uses the OpenAI Chat Completions API. Set:

```bash
export OPENAI_API_KEY=your_openai_key
export OPENAI_MODEL=gpt-5.3
```

If `OPENAI_MODEL` is not set, `search.py` defaults to `gpt-5.3`.

## Start The MCP Server

### Local stdio server

For `stdio`, you usually do not start the server manually. The client starts it as a subprocess:

```bash
python -m mcp_client mcp_server/main.py --members
```

You can also run the server directly, but it will wait for MCP JSON-RPC messages on stdin:

```bash
python mcp_server/main.py
```

### Streamable HTTP server

Use this for hosted or production-like MCP behavior:

```bash
python mcp_server/main.py --transport streamable-http --host 127.0.0.1 --port 8000
```

The MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

### Legacy SSE server

Use this only for MCP clients that specifically require SSE:

```bash
python mcp_server/main.py --transport sse --host 127.0.0.1 --port 8000
```

The SSE endpoint is:

```text
http://127.0.0.1:8000/sse
```

## Run The MCP Client

### List server members over stdio

This starts `mcp_server/main.py` as a subprocess and lists tools, prompts, and resources:

```bash
python -m mcp_client mcp_server/main.py --members
```

Module path also works:

```bash
python -m mcp_client mcp_server.main --members
```

### List server members over Streamable HTTP

Start the server first:

```bash
python mcp_server/main.py --transport streamable-http --host 127.0.0.1 --port 8000
```

Then connect the client:

```bash
python -m mcp_client http://127.0.0.1:8000/mcp --members
```

### List server members over SSE

Start the SSE server first:

```bash
python mcp_server/main.py --transport sse --host 127.0.0.1 --port 8000
```

Then connect the client:

```bash
python -m mcp_client http://127.0.0.1:8000/sse --members
```

## Chat Mode

Chat mode uses OpenAI Chat Completions and the MCP tools exposed by the server.

### Chat over stdio

```bash
OPENAI_API_KEY=your_openai_key python -m mcp_client mcp_server/main.py --chat
```

### Chat over Streamable HTTP

Start the server:

```bash
python mcp_server/main.py --transport streamable-http --host 127.0.0.1 --port 8000
```

Run the client:

```bash
OPENAI_API_KEY=your_openai_key python -m mcp_client http://127.0.0.1:8000/mcp --chat
```

### Chat over SSE

Start the server:

```bash
python mcp_server/main.py --transport sse --host 127.0.0.1 --port 8000
```

Run the client:

```bash
OPENAI_API_KEY=your_openai_key python -m mcp_client http://127.0.0.1:8000/sse --chat
```

## Prompt Mode

The server exposes reusable MCP prompts. List them with:

```bash
python -m mcp_client mcp_server/main.py --members
```

Fetch the portfolio summary prompt:

```bash
python -m mcp_client mcp_server/main.py \
  --prompt portfolio_summary_prompt \
  --prompt-arg portfolio_name=Main
```

## Portfolio Transaction Tool

The `add_entry_to_portfolio` tool needs a platform auth token. Set it before using chat mode for portfolio writes:

```bash
export PLATFORM_API_BASE_URL=https://your-platform.example/api
export PLATFORM_AUTH_TOKEN=your_platform_token
```

Example:

```bash
OPENAI_API_KEY=your_openai_key \
PLATFORM_API_BASE_URL=https://your-platform.example/api \
PLATFORM_AUTH_TOKEN=your_platform_token \
python -m mcp_client http://127.0.0.1:8000/mcp --chat
```

## Token Lookup

The server exposes `search_coingecko_tokens` to resolve user-provided token names or symbols to CoinGecko token IDs.

The tool uses CoinGecko's public search endpoint:

```text
https://api.coingecko.com/api/v3/search
```

Example user request in chat:

```text
Add 2 HYPE to my Main portfolio at $30 on May 15, 2026
```

The assistant should use `search_coingecko_tokens` to resolve `HYPE` before creating the portfolio transaction. If CoinGecko returns multiple plausible matches, the assistant should ask the user to choose instead of guessing.

The transaction tool accepts either `portfolio_id` or `portfolio_name`. For chat usage, prefer `portfolio_name`; the server can resolve it with the authenticated platform portfolio lookup before submitting the transaction.

## Portfolio Stats

The server exposes `get_portfolio_stats` for read-only portfolio reporting. It accepts either `portfolio_id` or `portfolio_name`.

Internally it calls:

```text
${PLATFORM_API_BASE_URL}/portfolios/<portfolio_id>/
${PLATFORM_API_BASE_URL}/portfolio-trends/<portfolio_id>/?period=24h
```

Example chat request:

```text
Show me total stats for my Main portfolio
```

The tool returns portfolio totals, allocation, compact asset stats, and optional trend values. Large token fields such as 7-day sparklines are omitted from the returned `cryptoAssets` summary to keep the model context manageable.

## Transport Selection

The client auto-detects the transport:

- Local file/module path: `stdio`
- `http://.../mcp`: Streamable HTTP
- `http://.../sse`: SSE

You can override detection:

```bash
python -m mcp_client http://127.0.0.1:8000/mcp --transport streamable-http --members
python -m mcp_client http://127.0.0.1:8000/sse --transport sse --members
python -m mcp_client mcp_server/main.py --transport stdio --members
```

The server also supports environment variables:

```bash
MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 MCP_PORT=8000 python mcp_server/main.py
```

## Tests

Run the MCP server connection test:

```bash
pytest mcp_server/tests/test_server.py
```
