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

The config supports multiple accounts per source:

```yaml
exchanges:
  binance:
    accounts:
      - id: binance-main
        label: Binance Main
        enabled: true
        environment: production
        apiKey: "read-only-key"
        apiSecret: "read-only-secret"

  okx:
    accounts:
      - id: okx-main
        label: OKX Main
        enabled: true
        domain: https://www.okx.com
        apiKey: "read-only-key"
        apiSecret: "read-only-secret"
        passphrase: "api-passphrase"

brokers:
  moomoo:
    accounts:
      - id: moomoo-us
        label: moomoo US
        enabled: true
        host: 127.0.0.1
        port: 11111
        trdMarket: US
        securityFirm: FUTUSECURITIES

  longbridge:
    accounts:
      - id: longbridge-main
        label: Longbridge Main
        enabled: true
        appKey: "longbridge-app-key"
        appSecret: "longbridge-app-secret"
        accessToken: "longbridge-access-token"

manual:
  accounts:
    - id: bank-cmb
      label: China Merchants Bank
      enabled: true
      category: cash
      assets:
        - symbol: CNY
          name: Checking
          quantity: 50000
          currency: CNY
```

Each account `id` must be unique and stable. This id appears in MCP responses
and is used for filtering.

For manual assets in non-USD currencies, add rates under `rates`:

```yaml
rates:
  USD: 1
  USDT: 1
  CNY: 0.138
  HKD: 0.128
  SGD: 0.74
```

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

## Security Notes

- Use read-only API keys for exchanges.
- Do not commit `config.local.yaml`.
- Do not enable withdrawal, transfer, or trading permissions on API keys.
- Use Longbridge API key credentials with read-only permissions where possible.
- Bank and Alipay balances are manual entries only; this project does not scrape
  or automate those services.
