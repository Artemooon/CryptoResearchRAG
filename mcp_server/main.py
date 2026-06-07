import asyncio
import os
import sys
from argparse import ArgumentParser
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests
from mcp.server.fastmcp import FastMCP

sys.path.append(str(Path(__file__).resolve().parent.parent))
from platform_config import PLATFORM_AUTH_TOKEN_ENV, build_platform_api_url, get_platform_auth_token


mcp = FastMCP("ecommerce")


def _error_payload(message: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"ok": False, "error": message}
    payload.update(extra)
    return payload


def _success_payload(*, response: requests.Response, payload: dict[str, object]) -> dict[str, object]:
    try:
        response_body = response.json()
    except ValueError:
        response_body = response.text

    return {
        "ok": True,
        "status_code": response.status_code,
        "request_payload": payload,
        "response": response_body,
    }


def _summarize_crypto_asset(asset: dict) -> dict:
    token = asset.get("token") or {}
    return {
        "asset_id": asset.get("id"),
        "token": {
            "id": token.get("id"),
            "name": token.get("name"),
            "symbol": token.get("symbol"),
            "currentPrice": token.get("currentPrice"),
            "priceChangePercentage1HInCurrency": token.get("priceChangePercentage1HInCurrency"),
            "priceChangePercentage24HInCurrency": token.get("priceChangePercentage24HInCurrency"),
            "priceChangePercentage7DInCurrency": token.get("priceChangePercentage7DInCurrency"),
            "marketCap": token.get("marketCap"),
        },
        "hold": asset.get("hold"),
        "currentValue": asset.get("currentValue"),
        "totalCostUsd": asset.get("totalCostUsd"),
        "assetWeight": asset.get("assetWeight"),
        "avgEntryPrice": asset.get("avgEntryPrice"),
        "avgExitPrice": asset.get("avgExitPrice"),
        "pnlUsd": asset.get("pnlUsd"),
        "pnlPercentage": asset.get("pnlPercentage"),
        "realizedPnl": asset.get("realizedPnl"),
        "unrealizedPnl": asset.get("unrealizedPnl"),
    }


@mcp.tool()
async def search_coingecko_tokens(query: str, max_results: int = 10) -> dict:
    """Search CoinGecko tokens by name, symbol, contract address, or CoinGecko ID."""

    normalized_query = query.strip()
    if not normalized_query:
        return _error_payload("query must not be empty")

    if max_results < 1:
        return _error_payload(
            "max_results must be at least 1",
            max_results=max_results,
        )

    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/search",
            params={"query": normalized_query},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        status_code = response.status_code if response is not None else None
        response_text = response.text if response is not None else str(exc)
        return _error_payload(
            "CoinGecko rejected the token search",
            status_code=status_code,
            response_text=response_text,
            query=normalized_query,
        )
    except requests.RequestException as exc:
        return _error_payload(
            "Could not reach CoinGecko",
            query=normalized_query,
            request_error=str(exc),
        )

    try:
        data = resp.json()
    except ValueError:
        return _error_payload(
            "CoinGecko returned a non-JSON response",
            status_code=resp.status_code,
            response_text=resp.text,
            query=normalized_query,
        )

    coins = data.get("coins", [])
    limited_coins = coins[:max_results]

    return {
        "ok": True,
        "query": normalized_query,
        "count": len(coins),
        "coins": [
            {
                "id": coin.get("id"),
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "api_symbol": coin.get("api_symbol"),
                "market_cap_rank": coin.get("market_cap_rank"),
                "thumb": coin.get("thumb"),
                "large": coin.get("large"),
            }
            for coin in limited_coins
        ],
    }

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


@mcp.prompt()
def portfolio_summary_prompt(portfolio_name: str) -> str:
    """Create a concise portfolio summary prompt."""
    return (
        f"Analyze the portfolio named {portfolio_name}. "
        "Summarize total value, largest positions, risk concentration, "
        "recent changes, and notable missing context. "
        "Do not give financial advice. Keep the answer concise."
    )


@mcp.tool()
async def resolve_portfolio_id_from_name(
  portfolio_name: str,
  page_size: int = 100,
  auth_token: str | None = None,
) -> dict:
    """Resolve a platform portfolio name to its portfolio ID."""

    token = get_platform_auth_token(auth_token)
    if not token:
      return _error_payload(
          "Missing platform auth token",
          hint=f"Set {PLATFORM_AUTH_TOKEN_ENV} or pass auth_token explicitly.",
      )

    request_info = {
      "method": "GET",
      "url": build_platform_api_url("/portfolios/"),
      "params": {"page_size": page_size},
      "auth_token_present": True,
    }

    try:
      resp = requests.get(
          request_info["url"],
          headers={"Authorization": f"Token {token}"},
          params=request_info["params"],
          timeout=30,
      )
      resp.raise_for_status()
    except requests.HTTPError as exc:
      response = exc.response
      return _error_payload(
          "Platform rejected the portfolio lookup",
          status_code=response.status_code if response is not None else None,
          response_text=response.text if response is not None else str(exc),
          request=request_info,
      )
    except requests.RequestException as exc:
      return _error_payload(
          "Could not reach platform",
          request_error=str(exc),
          request=request_info,
      )

    try:
      data = resp.json()
    except ValueError:
      return _error_payload(
          "Platform returned a non-JSON portfolio lookup response",
          status_code=resp.status_code,
          response_text=resp.text,
          request=request_info,
      )
    portfolios = data.get("results", [])

    matches = [
      portfolio
      for portfolio in portfolios
      if portfolio.get("name", "").casefold() == portfolio_name.casefold()
    ]

    if not matches:
      return _error_payload(
          "Could not find portfolio with the provided name",
          portfolio_name=portfolio_name,
          available_portfolios=[
              {"id": p.get("id"), "name": p.get("name")}
              for p in portfolios
          ],
      )

    if len(matches) > 1:
      return _error_payload(
          "Multiple portfolios matched the provided name",
          portfolio_name=portfolio_name,
          matches=[
              {"id": p.get("id"), "name": p.get("name")}
              for p in matches
          ],
      )

    portfolio = matches[0]
    return {
      "ok": True,
      "portfolio_id": portfolio.get("id"),
      "portfolio_name": portfolio.get("name"),
    }


async def _resolve_portfolio_id(
    *,
    portfolio_id: int | None,
    portfolio_name: str | None,
    auth_token: str,
    request_payload: dict[str, object],
) -> int | dict:
    if portfolio_id is not None:
        return portfolio_id

    if not portfolio_name:
        return _error_payload(
            "Either portfolio_id or portfolio_name is required",
            request_payload=request_payload,
        )

    resolved = await resolve_portfolio_id_from_name(
        portfolio_name=portfolio_name,
        auth_token=auth_token,
    )
    if not resolved.get("ok"):
        return _error_payload(
            "Could not resolve portfolio_name to portfolio_id",
            resolution=resolved,
            request_payload=request_payload,
        )

    resolved_portfolio_id = resolved.get("portfolio_id")
    if resolved_portfolio_id is None:
        return _error_payload(
            "Portfolio lookup succeeded but did not return an id",
            resolution=resolved,
            request_payload=request_payload,
        )

    return int(resolved_portfolio_id)


@mcp.tool()
async def get_portfolio_stats(
    portfolio_id: int | None = None,
    portfolio_name: str | None = None,
    include_trends: bool = True,
    trend_period: str = "24h",
    auth_token: str | None = None,
) -> dict:
    """Get platform portfolio totals, allocation, asset stats, and optional trend data."""

    token = get_platform_auth_token(auth_token)
    request_payload = {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio_name,
        "include_trends": include_trends,
        "trend_period": trend_period,
    }

    if not token:
        return _error_payload(
            "Missing platform auth token",
            hint=f"Set {PLATFORM_AUTH_TOKEN_ENV} or pass auth_token explicitly.",
            request_payload=request_payload,
        )

    resolved_portfolio_id = await _resolve_portfolio_id(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        auth_token=token,
        request_payload=request_payload,
    )
    if isinstance(resolved_portfolio_id, dict):
        return resolved_portfolio_id

    portfolio_request = {
        "method": "GET",
        "url": build_platform_api_url(f"/portfolios/{resolved_portfolio_id}/"),
        "auth_token_present": True,
    }

    try:
        resp = requests.get(
            portfolio_request["url"],
            headers={"Authorization": f"Token {token}"},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        return _error_payload(
            "Platform rejected the portfolio stats lookup",
            status_code=response.status_code if response is not None else None,
            response_text=response.text if response is not None else str(exc),
            request=portfolio_request,
            request_payload=request_payload,
        )
    except requests.RequestException as exc:
        return _error_payload(
            "Could not reach platform",
            request_error=str(exc),
            request=portfolio_request,
            request_payload=request_payload,
        )

    try:
        portfolio = resp.json()
    except ValueError:
        return _error_payload(
            "Platform returned a non-JSON portfolio stats response",
            status_code=resp.status_code,
            response_text=resp.text,
            request=portfolio_request,
            request_payload=request_payload,
        )

    result = {
        "ok": True,
        "portfolio": {
            "id": portfolio.get("id"),
            "name": portfolio.get("name"),
            "totalBalance": portfolio.get("totalBalance"),
            "pnlUsd": portfolio.get("pnlUsd"),
            "pnlPercentage": portfolio.get("pnlPercentage"),
            "change24HUsd": portfolio.get("change24HUsd"),
            "change24HPercentage": portfolio.get("change24HPercentage"),
            "isEmpty": portfolio.get("isEmpty"),
            "created": portfolio.get("created"),
            "updated": portfolio.get("updated"),
            "periods": portfolio.get("periods"),
        },
        "allocation": portfolio.get("allocation") or {},
        "cryptoAssets": [
            _summarize_crypto_asset(asset)
            for asset in portfolio.get("cryptoAssets", [])
        ],
    }

    if not include_trends:
        return result

    trends_request = {
        "method": "GET",
        "url": build_platform_api_url(f"/portfolio-trends/{resolved_portfolio_id}/"),
        "params": {"period": trend_period},
        "auth_token_present": True,
    }

    try:
        trends_resp = requests.get(
            trends_request["url"],
            headers={"Authorization": f"Token {token}"},
            params=trends_request["params"],
            timeout=30,
        )
        trends_resp.raise_for_status()
        trends = trends_resp.json()
        result["trends"] = {
            "period": trend_period,
            "values": trends.get("trends", {}),
        }
    except requests.HTTPError as exc:
        response = exc.response
        result["trends_error"] = _error_payload(
            "Platform rejected the portfolio trends lookup",
            status_code=response.status_code if response is not None else None,
            response_text=response.text if response is not None else str(exc),
            request=trends_request,
        )
    except requests.RequestException as exc:
        result["trends_error"] = _error_payload(
            "Could not reach platform portfolio trends",
            request_error=str(exc),
            request=trends_request,
        )
    except ValueError:
        result["trends_error"] = _error_payload(
            "Platform returned a non-JSON portfolio trends response",
            status_code=trends_resp.status_code,
            response_text=trends_resp.text,
            request=trends_request,
        )

    return result


@mcp.tool()
async def add_entry_to_portfolio(
    purchase_price: str,
    quantity: str,
    token_id: str,
    transaction_date: str,
    transaction_type: str,
    portfolio_id: int | None = None,
    portfolio_name: str | None = None,
    auth_token: str | None = None,
) -> dict:
    """Create a platform portfolio transaction using either a portfolio ID or portfolio name."""

    try:
        Decimal(purchase_price)
        Decimal(quantity)
    except InvalidOperation:
        return _error_payload(
            "purchase_price and quantity must be decimal strings",
            field_errors={
                "purchase_price": purchase_price,
                "quantity": quantity,
            },
        )

    token = get_platform_auth_token(auth_token)
    request_payload = {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio_name,
        "purchase_price": purchase_price,
        "quantity": quantity,
        "token_id": token_id,
        "transaction_date": transaction_date,
        "transaction_type": transaction_type,
    }

    if not token:
        return _error_payload(
            "Missing platform auth token",
            hint=f"Set {PLATFORM_AUTH_TOKEN_ENV} or pass auth_token explicitly.",
            request_payload=request_payload,
        )

    resolved_portfolio_id = await _resolve_portfolio_id(
        portfolio_id=portfolio_id,
        portfolio_name=portfolio_name,
        auth_token=token,
        request_payload=request_payload,
    )
    if isinstance(resolved_portfolio_id, dict):
        return resolved_portfolio_id

    payload = {
        "portfolio_id": resolved_portfolio_id,
        "purchase_price": purchase_price,
        "quantity": quantity,
        "token_id": token_id,
        "transaction_date": transaction_date,
        "transaction_type": transaction_type,
    }

    try:
        resp = requests.post(
            build_platform_api_url("/portfolio-transactions/"),
            headers={"Authorization": f"Token {token}"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        response = exc.response
        status_code = response.status_code if response is not None else None
        response_text = response.text if response is not None else str(exc)
        return _error_payload(
            "Platform rejected the portfolio transaction",
            status_code=status_code,
            response_text=response_text,
            request_payload=payload,
        )
    except requests.RequestException as exc:
        return _error_payload(
            "Could not reach platform",
            request_payload=payload,
            request_error=str(exc),
        )

    return _success_payload(response=resp, payload=payload)

def _parse_args():
    parser = ArgumentParser(description="Run the ecommerce MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="MCP transport to use. Defaults to MCP_TRANSPORT or stdio.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="HTTP host for sse/streamable-http transports.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8000")),
        help="HTTP port for sse/streamable-http transports.",
    )
    parser.add_argument(
        "--mount-path",
        default=os.environ.get("MCP_MOUNT_PATH"),
        help="Optional mount path for SSE transport.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport, mount_path=args.mount_path)
