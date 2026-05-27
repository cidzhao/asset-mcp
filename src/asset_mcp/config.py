from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SECRET_KEYS = {"apikey", "apisecret", "passphrase", "secret", "token", "password"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BinanceAccountConfig:
    id: str
    label: str
    apiKey: str
    apiSecret: str
    enabled: bool = True
    environment: str = "production"


@dataclass(frozen=True)
class OkxAccountConfig:
    id: str
    label: str
    apiKey: str
    apiSecret: str
    passphrase: str
    enabled: bool = True
    environment: str = "production"
    domain: str = "https://www.okx.com"


@dataclass(frozen=True)
class MoomooAccountConfig:
    id: str
    label: str
    host: str = "127.0.0.1"
    port: int = 11111
    trdMarket: str = "US"
    securityFirm: str = "FUTUSECURITIES"
    accountId: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class ManualAssetConfig:
    symbol: str
    quantity: float
    currency: str
    name: str | None = None
    unitPriceUsd: float | None = None


@dataclass(frozen=True)
class ManualAccountConfig:
    id: str
    label: str
    category: str
    assets: list[ManualAssetConfig]
    enabled: bool = True


@dataclass(frozen=True)
class AppConfig:
    baseCurrency: str = "USD"
    rates: dict[str, float] = field(default_factory=lambda: {"USD": 1.0, "USDT": 1.0})
    binanceAccounts: list[BinanceAccountConfig] = field(default_factory=list)
    okxAccounts: list[OkxAccountConfig] = field(default_factory=list)
    moomooAccounts: list[MoomooAccountConfig] = field(default_factory=list)
    manualAccounts: list[ManualAccountConfig] = field(default_factory=list)


def default_config_path() -> Path:
    return Path(os.environ.get("ASSET_MCP_CONFIG", "config.local.yaml"))


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path is not None else default_config_path()
    if not config_path.exists():
        raise ConfigError(
            f"Config file not found: {config_path}. Copy config.example.yaml to config.local.yaml."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> AppConfig:
    rates = {
        str(currency).upper(): _as_float(rate, f"rates.{currency}")
        for currency, rate in (raw.get("rates") or {}).items()
    }
    rates.setdefault("USD", 1.0)
    rates.setdefault("USDT", 1.0)

    exchanges = raw.get("exchanges") or {}
    brokers = raw.get("brokers") or {}
    manual = raw.get("manual") or {}

    binance_accounts = [
        BinanceAccountConfig(
            id=_required_str(item, "id", "exchanges.binance.accounts[]"),
            label=str(item.get("label") or item.get("id")),
            enabled=bool(item.get("enabled", True)),
            environment=str(item.get("environment", "production")),
            apiKey=str(item.get("apiKey", "")),
            apiSecret=str(item.get("apiSecret", "")),
        )
        for item in _account_items(exchanges, "binance")
    ]

    okx_accounts = [
        OkxAccountConfig(
            id=_required_str(item, "id", "exchanges.okx.accounts[]"),
            label=str(item.get("label") or item.get("id")),
            enabled=bool(item.get("enabled", True)),
            environment=str(item.get("environment", "production")),
            domain=str(item.get("domain", "https://www.okx.com")).rstrip("/"),
            apiKey=str(item.get("apiKey", "")),
            apiSecret=str(item.get("apiSecret", "")),
            passphrase=str(item.get("passphrase", "")),
        )
        for item in _account_items(exchanges, "okx")
    ]

    moomoo_accounts = [
        MoomooAccountConfig(
            id=_required_str(item, "id", "brokers.moomoo.accounts[]"),
            label=str(item.get("label") or item.get("id")),
            enabled=bool(item.get("enabled", True)),
            host=str(item.get("host", "127.0.0.1")),
            port=int(item.get("port", 11111)),
            trdMarket=str(item.get("trdMarket", "US")),
            securityFirm=str(item.get("securityFirm", "FUTUSECURITIES")),
            accountId=_optional_int(item.get("accountId")),
        )
        for item in _account_items(brokers, "moomoo")
    ]

    manual_accounts = [
        ManualAccountConfig(
            id=_required_str(item, "id", "manual.accounts[]"),
            label=str(item.get("label") or item.get("id")),
            enabled=bool(item.get("enabled", True)),
            category=str(item.get("category", "manual")),
            assets=[
                ManualAssetConfig(
                    symbol=_required_str(asset, "symbol", f"manual.accounts[{item.get('id')}].assets[]"),
                    name=asset.get("name"),
                    quantity=_as_float(asset.get("quantity", 0), "manual.assets[].quantity"),
                    currency=str(asset.get("currency") or asset.get("symbol")).upper(),
                    unitPriceUsd=_optional_float(asset.get("unitPriceUsd")),
                )
                for asset in item.get("assets", [])
            ],
        )
        for item in manual.get("accounts", [])
    ]

    config = AppConfig(
        baseCurrency=str(raw.get("baseCurrency", "USD")).upper(),
        rates=rates,
        binanceAccounts=binance_accounts,
        okxAccounts=okx_accounts,
        moomooAccounts=moomoo_accounts,
        manualAccounts=manual_accounts,
    )
    validate_unique_account_ids(config)
    return config


def validate_unique_account_ids(config: AppConfig) -> None:
    seen: dict[str, str] = {}
    all_accounts = [
        ("binance", config.binanceAccounts),
        ("okx", config.okxAccounts),
        ("moomoo", config.moomooAccounts),
        ("manual", config.manualAccounts),
    ]
    for source, accounts in all_accounts:
        for account in accounts:
            if account.id in seen:
                raise ConfigError(
                    f"Duplicate account id '{account.id}' in {source}; already used by {seen[account.id]}."
                )
            seen[account.id] = source


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if str(key).lower() in SECRET_KEYS else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def _account_items(section: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return list(((section.get(key) or {}).get("accounts") or []))


def _required_str(item: dict[str, Any], key: str, location: str) -> str:
    value = item.get(key)
    if value is None or str(value).strip() == "":
        raise ConfigError(f"Missing required field '{key}' in {location}.")
    return str(value)


def _as_float(value: Any, location: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Expected number at {location}.") from exc


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
