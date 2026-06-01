# Asset MCP

[中文文档](https://github.com/cidzhao/asset-mcp/blob/main/README_zh.md)

Read-only Python MCP server for aggregating personal assets across Binance, OKX,
moomoo OpenD, Longbridge, IBKR, on-chain wallets, and manually configured
accounts.

The server exposes normalized asset data to any MCP-compatible AI client. It
does not trade, transfer, withdraw, or automate bank/Alipay access.

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

## Requirements

- Python `>=3.10`.
- Read-only Binance/OKX API keys if enabling exchange accounts.
- moomoo/Futu OpenD installed, running, and logged in if enabling moomoo
  accounts.
- Longbridge OpenAPI API key credentials if enabling Longbridge accounts.
- IBKR Flex Web Service token and Flex Query ID if enabling IBKR accounts.
- Public wallet addresses if enabling on-chain wallet accounts.
- `uv` is only required for local development; end users can install with
  `pip`.

## Quick Start

```bash
# 1. Install from PyPI
pip install asset-mcp

# 2. Create the starter config (~/.config/asset-mcp/config.local.yaml)
asset-mcp init

# 3. Edit the config: fill in credentials for at least one account
#    and set its `enabled: true`. See "Configure" below for per-provider examples.
vim ~/.config/asset-mcp/config.local.yaml

# 4. Register the server with your MCP client
claude mcp add asset-mcp -- asset-mcp
# or
codex mcp add asset-mcp -- asset-mcp

# 5. Verify: ask your client to call the `health_check_sources` tool.
#    Every enabled account should return `ok: true`.
```

![Install and register](https://raw.githubusercontent.com/cidzhao/asset-mcp/main/media/quick-start.gif)

The smallest working setup needs no API keys — a single manual cash account is
enough to confirm the install:

```yaml
baseCurrency: USD
rates:
  USD: 1.0
  CNY: 0.14
manual:
  accounts:
    - id: cash
      label: Cash on hand
      enabled: true
      category: cash
      assets:
        - symbol: CNY
          quantity: 10000
          currency: CNY
```

## Install

Install from PyPI:

```bash
pip install asset-mcp
```

The base installation works with Binance, OKX, IBKR, on-chain wallets, and
manual accounts. The moomoo and Longbridge SDKs are optional extras — install
them only when needed:

```bash
pip install "asset-mcp[moomoo]"
pip install "asset-mcp[longbridge]"
pip install "asset-mcp[moomoo,longbridge]"
```

Existing config files are never overwritten by `asset-mcp init` unless you pass
`--force`:

```bash
asset-mcp init --force
```

For local development, clone the repository and install dependencies with
[`uv`](https://docs.astral.sh/uv/):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # if uv is not installed
uv sync --extra dev --extra moomoo --extra longbridge
uv run asset-mcp init --path config.local.yaml
```

If you do not need moomoo or Longbridge support, omit those optional extras:

```bash
uv sync --extra dev
```

## Configure

`asset-mcp init` writes the starter template to
`~/.config/asset-mcp/config.local.yaml`. Pass `--path <file>` to write the
template anywhere other than the default location.

If you installed from PyPI, `asset-mcp init` writes the same template the
repository ships as `config.example.yaml`. Refer to that file on GitHub (see
**Links** below) for the complete set of supported fields and inline comments.

Keep real API keys and personal balances only in your local config file —
never commit it. Each account `id` must be unique and stable; this id appears
in MCP responses and is used for filtering.

### Binance

Create a **read-only** API key in the Binance API management console. Keep
Withdraw, Trade, Margin, and Futures permissions disabled.

```yaml
exchanges:
  binance:
    accounts:
      - id: binance-main
        label: Binance Main
        enabled: true
        apiKey: "replace-with-read-only-key"
        apiSecret: "replace-with-read-only-secret"
        # environment: production    # optional
```

### OKX

Create an OKX API key with **Read** permission only. The `passphrase` is the
one you chose when generating the key.

```yaml
exchanges:
  okx:
    accounts:
      - id: okx-main
        label: OKX Main
        enabled: true
        apiKey: "replace-with-read-only-key"
        apiSecret: "replace-with-read-only-secret"
        passphrase: "replace-with-passphrase"
        # domain: https://www.okx.com   # optional
```

### moomoo (OpenD)

Install and start the
[Futu/moomoo OpenD](https://openapi.futunn.com/futu-api-doc/quick/opend-base.html)
client and log in before launching `asset-mcp`. Install the optional SDK with
`pip install "asset-mcp[moomoo]"`.

```yaml
brokers:
  moomoo:
    accounts:
      - id: moomoo-us
        label: moomoo US
        enabled: true
        host: 127.0.0.1
        port: 11111
        trdMarket: US                # US / HK / CN / SG
        securityFirm: FUTUSECURITIES # or FUTUINC / MOOMOOSG / FUTUSG
        # accountId: 12345678        # optional; only needed for multi-account setups
```

### Longbridge

Create a Longbridge OpenAPI application with read-only scopes and copy the App
Key, App Secret, and Access Token. Install the optional SDK with
`pip install "asset-mcp[longbridge]"`.

```yaml
brokers:
  longbridge:
    accounts:
      - id: longbridge-main
        label: Longbridge Main
        enabled: true
        appKey: "replace-with-app-key"
        appSecret: "replace-with-app-secret"
        accessToken: "replace-with-access-token"
```

### IBKR

IBKR support uses Flex Web Service. In IBKR Client Portal, enable Flex Web
Service, create an Activity Flex Query that outputs XML, and include at least
Cash Report and Open Positions. Then configure the generated token and query
ID under `brokers.ibkr.accounts`:

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

### On-chain wallets

Configure public wallet addresses under `onchain.accounts`. The provider
discovers assets held by each address. EVM chains query native balances plus a
built-in mainstream ERC-20 token list, and any ERC-20 contracts explicitly
configured under the address. Solana uses `getTokenAccountsByOwner` for SPL
token accounts. Bitcoin and TRON use public address APIs. No private keys,
seed phrases, trading, transfer, or approval operations are supported.

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
node or paid provider over the default public endpoints. Native token prices
are read from `rates` first, then CoinGecko. Solana SPL tokens without a
Jupiter price are still returned with zero USD value.

For configured ERC-20 tokens, `symbol`, `contractAddress`, and `decimals` are
required. `name` is optional. Add `coinGeckoId` for live USD pricing, or
provide the token price under `rates`; if no price is available the token is
still returned with zero USD value. If a Covalent indexer is enabled,
configured ERC-20 contracts are queried in addition to the indexed inventory,
skipping contracts already returned by the indexer.

For an Etherscan-like full token inventory instead of the built-in mainstream
EVM token list, configure an optional indexer:

```yaml
onchain:
  indexer:
    provider: covalent
    apiKey: "replace-with-covalent-api-key"
```

### Manual assets & rates

USD value for each manual asset is computed as `quantity * rates[currency]`.
On-chain native tokens read `rates` first and fall back to CoinGecko.

```yaml
rates:
  USD: 1.0
  CNY: 0.14
  HKD: 0.128

manual:
  accounts:
    - id: alipay
      label: Alipay
      enabled: true
      category: cash
      assets:
        - symbol: CNY
          quantity: 25000
          currency: CNY
    - id: home
      label: Primary residence
      enabled: true
      category: property
      assets:
        - symbol: USD
          quantity: 500000
          currency: USD
```

## Run the MCP Server

```bash
asset-mcp
```

By default the server reads config in this order:

1. `ASSET_MCP_CONFIG`
2. `config.local.yaml` in the current directory
3. `~/.config/asset-mcp/config.local.yaml`

To use another path:

```bash
ASSET_MCP_CONFIG=/path/to/config.local.yaml asset-mcp
```

## MCP Client Configuration

Use stdio transport. Example client configuration:

```json
{
  "mcpServers": {
    "asset-mcp": {
      "command": "asset-mcp"
    }
  }
}
```

If you prefer a non-default config path, pass an absolute path through
`ASSET_MCP_CONFIG`.

## MCP Tools

- `get_net_worth`: total net worth and grouped summaries.
- `get_assets`: normalized asset rows with optional filters.
- `get_asset_dashboard_data`: chart-ready grouping data.
- `health_check_sources`: per-account configuration and connection status.

Provider calls are isolated with per-provider timeouts. When querying multiple
providers, a slow or unavailable source is reported in `providerErrors` and
the tool returns the data that was available with `partial: true`. SDK-backed
providers that can block or emit native stdout run in a subprocess, so
timed-out requests can be terminated without leaving the MCP server blocked or
corrupting stdio transport.

`providerErrors` entries include stable machine-readable codes:

| code | Meaning | Retryable |
| --- | --- | --- |
| `provider_timeout` | The provider did not return before the per-provider timeout. | Yes |
| `provider_exception` | The provider raised an exception. Raw errors are sanitized. | No |
| `provider_exited` | A subprocess-isolated provider exited without returning a result. | Yes |

Example prompt after connecting the MCP server:

```text
Use asset-mcp to summarize my net worth by account and asset category.
```

To verify your setup end-to-end, ask the MCP client to call
`health_check_sources`. Every enabled account should return `ok: true`;
anything else points at a misconfiguration or unreachable provider.

## Troubleshooting

- **`health_check_sources` returns `configured: false` for every account.**
  Confirm the config file is in one of the three resolved locations
  (`ASSET_MCP_CONFIG`, the current directory, or
  `~/.config/asset-mcp/config.local.yaml`) and that each account has
  `enabled: true`.
- **moomoo accounts report `provider_exited` or `provider_timeout`.** OpenD
  is not running, not logged in, or the port is blocked. Verify the daemon
  with `nc -z 127.0.0.1 11111` and confirm you installed the SDK extras:
  `pip install "asset-mcp[moomoo]"`.
- **Responses include `partial: true` and a `providerErrors` array.** One or
  more providers failed. `provider_timeout` is safe to retry;
  `provider_exception` usually means an expired or wrong credential;
  `provider_exited` indicates a subprocess-isolated provider crashed (often
  moomoo/Longbridge SDK issues).
- **The MCP client shows "Transport closed" right after connecting.** A
  provider likely wrote a banner or warning to stdout and corrupted the
  JSON-RPC stream. Run `ASSET_MCP_CONFIG=config.local.yaml asset-mcp` in a
  terminal and look for any unexpected output before the first JSON frame.
- **An on-chain address shows zero balance even though it holds tokens.**
  Verify the `chain` value matches one of the supported aliases, and that any
  custom ERC-20 entry has all three of `symbol`, `contractAddress`, and
  `decimals`.

## Security Notes

- Use read-only API keys for exchanges.
- Do not commit `config.local.yaml`.
- Do not enable withdrawal, transfer, or trading permissions on API keys.
- Use Longbridge API key credentials with read-only permissions where
  possible.
- Use IBKR Flex Web Service only for read-only reporting queries.
- Bank and Alipay balances are manual entries only; this project does not
  scrape or automate those services.
- On-chain wallet support is address-based and read-only. Do not enter
  private keys or seed phrases in the config.

## Links

- Source code: https://github.com/cidzhao/asset-mcp
- Issues: https://github.com/cidzhao/asset-mcp/issues
- PyPI: https://pypi.org/project/asset-mcp/

---

## For Contributors

### Code Layout

- `src/asset_mcp/server.py`: MCP stdio entry point and tool definitions.
- `src/asset_mcp/service.py`: application service orchestration.
- `src/asset_mcp/domain/`: normalized models plus aggregation and filtering
  logic.
- `src/asset_mcp/config/`: config models, YAML parsing, validation, and
  secret redaction.
- `src/asset_mcp/providers/registry.py`: source-to-provider factory registry.
- `src/asset_mcp/providers/exchanges/`: crypto exchange providers, currently
  Binance and OKX.
- `src/asset_mcp/providers/brokerages/`: brokerage providers, currently
  moomoo, Longbridge, and IBKR.
- `src/asset_mcp/providers/onchain/`: on-chain wallet provider and
  chain-specific package boundaries.
- `src/asset_mcp/providers/manual/`: manually configured asset provider.
- `tests/config/`, `tests/domain/`, and `tests/providers/`: regression tests
  matching the source layout.

Compatibility re-export modules are kept for older imports such as
`asset_mcp.models`, `asset_mcp.aggregation`, and
`asset_mcp.providers.binance`. New code should prefer the package paths
above.

### Development

Install development dependencies before running tests:

```bash
uv sync --extra dev
```

The regression tests use fake provider clients and inline sample config data.
They do not require `config.local.yaml`, real API keys, running OpenD, broker
SDK sessions, or outbound network access.

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

### Release checklist

- Update the package version in both `pyproject.toml` and the fallback
  `__version__` value in `src/asset_mcp/__init__.py`.
- Run `uv run python -m compileall src tests` and `uv run pytest`.
- Run `uv build` and inspect the source distribution for local-only files
  before publishing.
- Publish from a GitHub release so the PyPI workflow builds, tests, and uploads
  the final artifacts.

### Adding Providers

- Add crypto exchanges under `src/asset_mcp/providers/exchanges/<platform>/`.
- Add brokerage integrations under
  `src/asset_mcp/providers/brokerages/<platform>/`.
- Add manual or on-chain behavior under their existing provider packages.
- Register the new source in `src/asset_mcp/providers/registry.py`.
- Extend config models/parsing under `src/asset_mcp/config/` when the
  provider needs new YAML fields.
- Add provider regression tests under `tests/providers/`.
- Preserve existing MCP response shapes and source names unless you
  intentionally change the public contract and update tests and docs
  together.

### Provider stdout hygiene

The MCP server uses stdio transport, so `stdout` is reserved for JSON-RPC
protocol frames. Any banner, warning, permission table, progress line, or
native SDK log written to `stdout` can corrupt the MCP stream and surface in
clients as `Transport closed`.

When adding a new broker or exchange provider:

- Wrap all third-party SDK calls with
  `asset_mcp.providers.stdio.redirect_sdk_stdout()`.
- Assume SDKs may bypass `print()` and write directly to file descriptor 1
  from native code or background threads; `contextlib.redirect_stdout()`
  alone is not enough.
- Exercise every network/API path, not only health checks. Quote/market-data
  endpoints often emit permission tables even when account-balance endpoints
  are quiet.
- Add a regression test using `capfd` and `os.write(1, ...)` to prove
  provider calls leave `stdout` empty.
