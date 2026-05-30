from __future__ import annotations

from asset_mcp.config.errors import ConfigError
from asset_mcp.config.models import AppConfig


def validate_unique_account_ids(config: AppConfig) -> None:
    seen: dict[str, str] = {}
    all_accounts = [
        ("binance", config.binanceAccounts),
        ("okx", config.okxAccounts),
        ("moomoo", config.moomooAccounts),
        ("longbridge", config.longbridgeAccounts),
        ("ibkr", config.ibkrAccounts),
        ("onchain", config.onchainAccounts),
        ("manual", config.manualAccounts),
    ]
    for source, accounts in all_accounts:
        for account in accounts:
            if account.id in seen:
                raise ConfigError(
                    f"Duplicate account id '{account.id}' in {source}; already used by {seen[account.id]}."
                )
            seen[account.id] = source
