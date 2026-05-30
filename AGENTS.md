# AGENTS.md

## Project Overview

Asset MCP is a read-only Python MCP server for aggregating personal asset data
across Binance, OKX, moomoo OpenD, Longbridge, IBKR, on-chain wallets, and
manually configured accounts.
It exposes normalized asset data, USD-denominated net worth summaries, and
dashboard-ready grouping data to MCP-compatible clients.

The server must not trade, transfer, withdraw, scrape banks, automate Alipay, or
perform any other asset-moving operation.

## Tech Stack

- Python `>=3.10`
- `uv` for dependency management and command execution
- `mcp` / FastMCP for the stdio MCP server
- `httpx` and provider SDKs for external account integrations
- `pytest`, `pytest-asyncio`, and `respx` for tests

## Important Paths

- `src/asset_mcp/server.py`: MCP tool definitions and server entry point.
- `src/asset_mcp/service.py`: service layer used by MCP tools.
- `src/asset_mcp/domain/aggregation.py`: asset grouping and summary logic.
- `src/asset_mcp/domain/models.py`: normalized domain models.
- `src/asset_mcp/config/`: YAML config parsing, config models, validation, and redaction.
- `src/asset_mcp/providers/registry.py`: source-to-provider factory registry.
- `src/asset_mcp/providers/exchanges/`: crypto exchange providers such as Binance and OKX.
- `src/asset_mcp/providers/brokerages/`: brokerage providers such as moomoo, Longbridge, and IBKR.
- `src/asset_mcp/providers/onchain/`: on-chain wallet provider and chain-specific adapters.
- `src/asset_mcp/providers/manual/`: manually configured asset provider.
- `src/asset_mcp/aggregation.py`, `src/asset_mcp/models.py`, and legacy
  `src/asset_mcp/providers/*.py` modules: compatibility re-exports for older
  imports. Prefer the package paths above for new code.
- `tests/config/`: config parser and validation regression tests.
- `tests/domain/`: domain model, filtering, and aggregation regression tests.
- `tests/providers/`: provider parsing, stdout hygiene, and fake-client integration tests.
- `config.example.yaml`: safe example config. Do not put real secrets here.

## Development Commands

Install dependencies:

```bash
uv sync --extra dev
```

Install all optional provider dependencies:

```bash
uv sync --extra dev --extra moomoo --extra longbridge
```

Run tests:

```bash
uv run pytest
```

Run a syntax check:

```bash
uv run python -m compileall src tests
```

Run the server with the example config:

```bash
ASSET_MCP_CONFIG=config.example.yaml uv run asset-mcp
```

## Code Guidelines

- Prefer existing provider and service patterns before adding new abstractions.
- Register new providers in `src/asset_mcp/providers/registry.py`; do not grow
  provider construction logic inside `src/asset_mcp/service.py`.
- Put crypto exchange integrations under `providers/exchanges/`, brokerage
  integrations under `providers/brokerages/`, on-chain logic under
  `providers/onchain/`, and manual sources under `providers/manual/`.
- Keep compatibility re-export modules small; platform implementation should
  live in the grouped provider package.
- Keep provider integrations read-only.
- Preserve normalized response shapes used by MCP tools unless the caller-facing
  contract is intentionally changed and tests are updated.
- Add or update tests for behavior changes, provider parsing changes, config
  validation changes, and regression fixes.
- When adding support for a new exchange, broker, manual source type, or other
  platform, update both `README.md` and `AGENTS.md` in the same change.
- Use structured parsing and typed models instead of ad hoc string handling when
  the codebase already has a suitable helper.
- Keep edits scoped. Do not rewrite unrelated provider, config, or aggregation
  code while making a targeted change.
- The checked-in tests should be runnable by a new contributor with
  `uv sync --extra dev` and `uv run pytest`. Do not require real API keys,
  `config.local.yaml`, a running broker app, or live network access for ordinary
  regression tests.

## Provider stdout Hygiene

The MCP server uses stdio transport, so `stdout` is reserved for JSON-RPC
protocol frames. Any banner, warning, permission table, progress line, or native
SDK log written to `stdout` can corrupt the MCP stream and surface in clients as
`Transport closed`.

When adding or changing a broker or exchange provider:

- Wrap all third-party SDK calls with
  `asset_mcp.providers.stdio.redirect_sdk_stdout()`.
- Assume SDKs may bypass `print()` and write directly to file descriptor 1 from
  native code or background threads; `contextlib.redirect_stdout()` alone is not
  enough.
- Exercise every network/API path, not only health checks. Quote/market-data
  endpoints can emit permission tables even when account-balance endpoints are
  quiet.
- Add a regression test using `capfd` and `os.write(1, ...)` to prove provider
  calls leave `stdout` empty.

## Security Rules

- Do not commit `config.local.yaml`.
- Do not commit real API keys, secrets, passphrases, access tokens, account
  numbers, personal balances, or private account labels.
- Use read-only API permissions for external services wherever possible.
- Do not add withdrawal, transfer, trading, order placement, or account mutation
  behavior.
- Return sanitized errors from MCP tools. Avoid leaking credentials or raw
  provider exception messages that may contain sensitive data.

## Agent Notes

- Check `git status --short` before editing and preserve unrelated user changes.
- Prefer `rg` / `rg --files` for repo searches.
- Read `README.md`, `pyproject.toml`, and relevant tests before changing public
  behavior.
- Run `uv run pytest` before finalizing code changes when practical.
