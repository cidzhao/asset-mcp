# Asset MCP

Read-only Python MCP server for aggregating personal assets across Binance, OKX,
moomoo OpenD, Longbridge, IBKR, on-chain wallets, and manually configured
accounts.

The server exposes normalized asset data to any MCP-compatible AI client. It does
not trade, transfer, withdraw, or automate bank/Alipay access.

## Features

- Multiple Binance accounts.
- Multiple OKX accounts.
- Multiple moomoo/Futu OpenD accounts.
- Multiple Longbridge OpenAPI accounts.
- Multiple IBKR Flex Web Service accounts.
- On-chain wallet addresses for BTC, ETH, SOL, BSC, TRON, Polygon, Avalanche,
  Arbitrum, Base, and Optimism.
- Manual assets for banks, Alipay, cash, property, and other offline accounts.
- USD-denominated net worth summaries.
- Dashboard-ready grouped data for AI-generated charts.

## Code Layout

- `src/asset_mcp/server.py`: MCP stdio entry point and tool definitions.
- `src/asset_mcp/service.py`: application service orchestration.
- `src/asset_mcp/domain/`: normalized models plus aggregation and filtering logic.
- `src/asset_mcp/config/`: config models, YAML parsing, validation, and secret redaction.
- `src/asset_mcp/providers/registry.py`: source-to-provider factory registry.
- `src/asset_mcp/providers/exchanges/`: crypto exchange providers, currently Binance and OKX.
- `src/asset_mcp/providers/brokerages/`: brokerage providers, currently moomoo, Longbridge, and IBKR.
- `src/asset_mcp/providers/onchain/`: on-chain wallet provider and chain-specific package boundaries.
- `src/asset_mcp/providers/manual/`: manually configured asset provider.
- `tests/config/`, `tests/domain/`, and `tests/providers/`: regression tests matching the source layout.

Compatibility re-export modules are kept for older imports such as
`asset_mcp.models`, `asset_mcp.aggregation`, and
`asset_mcp.providers.binance`. New code should prefer the package paths above.

## Requirements

- Python `>=3.10`.
- `uv` for dependency management and running commands.
- Read-only Binance/OKX API keys if enabling exchange accounts.
- moomoo/Futu OpenD installed, running, and logged in if enabling moomoo accounts.
- Longbridge OpenAPI API key credentials if enabling Longbridge accounts.
- IBKR Flex Web Service token and Flex Query ID if enabling IBKR accounts.
- Public wallet addresses if enabling on-chain wallet accounts.

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
`config.local.yaml`. Manual asset USD values are calculated as
`quantity * rates[currency]`.

For on-chain wallets, configure public addresses under `onchain.accounts`.
The provider discovers assets held by each address. EVM chains query native
balances plus a built-in mainstream ERC-20 token list, and any ERC-20 contracts
explicitly configured under the address. Solana uses
`getTokenAccountsByOwner` for SPL token accounts. Bitcoin and TRON use public
address APIs. No private keys, seed phrases, trading, transfer, or approval
operations are supported.

Supported built-in chains:

- `bitcoin` / `btc`
- `ethereum` / `eth` / `1`
- `solana` / `sol` / `501`
- `bsc` / `bnb` / `56`
- `tron` / `trx`
- `polygon` / `matic` / `137`
- `avalanche` / `avax` / `43114`
- `arbitrum` / `42161`
- `base` / `8453`
- `optimism` / `op` / `10`

Example on-chain wallet address config:

```yaml
onchain:
  accounts:
    - id: onchain-wallet
      label: On-chain Wallet
      enabled: true
      addresses:
        - chain: bitcoin
          address: "bc1..."
        - chain: ethereum
          address: "0x..."
          tokens:
            - symbol: CUSTOM
              name: Custom ERC-20 Token
              contractAddress: "0x..."
              decimals: 18
              coinGeckoId: ""
        - chain: solana
          address: "..."
        - chain: bsc
          address: "0x..."
```

Each address can override `rpcUrl` or `explorerApiUrl` if you prefer your own
node or paid provider over the default public endpoints. Native token prices are
read from `rates` first, then CoinGecko. Solana SPL tokens without a Jupiter
price are still returned with zero USD value.

For configured ERC-20 tokens, `symbol`, `contractAddress`, and `decimals` are
required. `name` is optional. Add `coinGeckoId` for live USD pricing, or provide
the token price under `rates`; if no price is available the token is still
returned with zero USD value. If a Covalent indexer is enabled, configured
ERC-20 contracts are queried in addition to the indexed inventory, skipping
contracts already returned by the indexer.

For an Etherscan-like full token inventory instead of the built-in mainstream
EVM token list, configure an optional indexer:

```yaml
onchain:
  indexer:
    provider: covalent
    apiKey: "replace-with-covalent-api-key"
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

### IBKR setup

IBKR support uses Flex Web Service. In IBKR Client Portal, enable Flex Web
Service, create an Activity Flex Query that outputs XML, and include at least
Cash Report and Open Positions. Then configure the generated token and query ID
under `brokers.ibkr.accounts`:

```yaml
brokers:
  ibkr:
    accounts:
      - id: ibkr-main
        label: IBKR Main
        enabled: true
        token: "replace-with-flex-web-service-token"
        queryId: "replace-with-flex-query-id"
        baseUrl: https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService
        accountId: U1234567
        version: 3
        statementRetries: 3
        statementRetryDelaySeconds: 5
```

Leave `accountId` empty to import every account included in the Flex Query, or
set it to keep only one account from a multi-account report. Flex Activity
Statement data is report data rather than a real-time feed, so use it for
periodic net-worth snapshots instead of active polling.

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

Install development dependencies before running tests:

```bash
uv sync --extra dev
```

The regression tests use fake provider clients and inline sample config data.
They do not require `config.local.yaml`, real API keys, running OpenD, broker SDK
sessions, or outbound network access.

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

Build local package artifacts:

```bash
uv build
```

This writes wheel and source distribution files under `dist/`.

### Adding Providers

- Add crypto exchanges under `src/asset_mcp/providers/exchanges/<platform>/`.
- Add brokerage integrations under `src/asset_mcp/providers/brokerages/<platform>/`.
- Add manual or on-chain behavior under their existing provider packages.
- Register the new source in `src/asset_mcp/providers/registry.py`.
- Extend config models/parsing under `src/asset_mcp/config/` when the provider
  needs new YAML fields.
- Add provider regression tests under `tests/providers/`.
- Preserve existing MCP response shapes and source names unless you intentionally
  change the public contract and update tests and docs together.

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
- Use IBKR Flex Web Service only for read-only reporting queries.
- Bank and Alipay balances are manual entries only; this project does not scrape
  or automate those services.
- On-chain wallet support is address-based and read-only. Do not enter private
  keys or seed phrases in the config.
