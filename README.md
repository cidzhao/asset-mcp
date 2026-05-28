# Asset MCP

Read-only Python MCP server for aggregating personal assets across Binance, OKX,
moomoo OpenD, Longbridge, and manually configured accounts.

The server exposes normalized asset data to any MCP-compatible AI client. It does
not trade, transfer, withdraw, or automate bank/Alipay access.

## Features

- Multiple Binance accounts.
- Multiple OKX accounts.
- Multiple moomoo/Futu OpenD accounts.
- Multiple Longbridge OpenAPI accounts.
- Manual assets for banks, Alipay, cash, property, and other offline accounts.
- USD-denominated net worth summaries.
- Dashboard-ready grouped data for AI-generated charts.

## Requirements

- Python `>=3.10`.
- `uv` for dependency management and running commands.
- Read-only Binance/OKX API keys if enabling exchange accounts.
- moomoo/Futu OpenD installed, running, and logged in if enabling moomoo accounts.
- Longbridge OpenAPI API key credentials if enabling Longbridge accounts.

Install `uv` if it is not already available:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Install

Clone the repository and install dependencies:

```bash
uv sync --extra dev --extra moomoo --extra longbridge
cp config.example.yaml config.local.yaml
```

If you do not need moomoo or Longbridge support, omit those optional extras:

```bash
uv sync --extra dev
```

Install Longbridge support with:

```bash
uv sync --extra dev --extra longbridge
```

## Configure

Copy the example config and edit local secrets/account data:

```bash
cp config.example.yaml config.local.yaml
```

`config.local.yaml` is ignored by git. Keep real API keys and personal balances
only in that file.

Use `config.example.yaml` as the source of truth for supported config fields.
Copy it to `config.local.yaml`, then edit account credentials, enabled flags,
manual assets, and currency rates as needed.

Each account `id` must be unique and stable. This id appears in MCP responses
and is used for filtering.

For manual assets in non-USD currencies, configure rates under `rates` in
`config.local.yaml`.

## Run the MCP Server

```bash
uv run asset-mcp
```

By default the server reads `config.local.yaml` from the current directory. To use
another path:

```bash
ASSET_MCP_CONFIG=/path/to/config.local.yaml uv run asset-mcp
```

## MCP Client Configuration

Use stdio transport. Example client configuration:

```json
{
  "mcpServers": {
    "asset-mcp": {
      "command": "uv",
      "args": ["run", "asset-mcp"],
      "cwd": "/absolute/path/to/calculate-assest",
      "env": {
        "ASSET_MCP_CONFIG": "/absolute/path/to/calculate-assest/config.local.yaml"
      }
    }
  }
}
```

If your MCP client does not support `cwd`, pass an absolute config path through
`ASSET_MCP_CONFIG`.

## MCP Tools

- `get_net_worth`: total net worth and grouped summaries.
- `get_assets`: normalized asset rows with optional filters.
- `get_asset_dashboard_data`: chart-ready grouping data.
- `health_check_sources`: per-account configuration and connection status.

Example prompt after connecting the MCP server:

```text
Use asset-mcp to summarize my net worth by account and asset category.
```

## Development

Run tests:

```bash
uv run pytest
```

Run a syntax check with Python's compiler:

```bash
uv run python -m compileall src tests
```

Run the server locally against the example config:

```bash
ASSET_MCP_CONFIG=config.example.yaml uv run asset-mcp
```

### Provider stdout hygiene

The MCP server uses stdio transport, so `stdout` is reserved for JSON-RPC
protocol frames. Any banner, warning, permission table, progress line, or native
SDK log written to `stdout` can corrupt the MCP stream and surface in clients as
`Transport closed`.

When adding a new broker or exchange provider:

- Wrap all third-party SDK calls with
  `asset_mcp.providers.stdio.redirect_sdk_stdout()`.
- Assume SDKs may bypass `print()` and write directly to file descriptor 1 from
  native code or background threads; `contextlib.redirect_stdout()` alone is not
  enough.
- Exercise every network/API path, not only health checks. Quote/market-data
  endpoints often emit permission tables even when account-balance endpoints are
  quiet.
- Add a regression test using `capfd` and `os.write(1, ...)` to prove provider
  calls leave `stdout` empty.

## Security Notes

- Use read-only API keys for exchanges.
- Do not commit `config.local.yaml`.
- Do not enable withdrawal, transfer, or trading permissions on API keys.
- Use Longbridge API key credentials with read-only permissions where possible.
- Bank and Alipay balances are manual entries only; this project does not scrape
  or automate those services.
