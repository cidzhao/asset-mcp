from __future__ import annotations

import asyncio
from typing import Any

from asset_mcp.aggregation import build_dashboard_data, build_net_worth, filter_assets
from asset_mcp.config import AppConfig, load_config
from asset_mcp.models import AccountStatus, Asset
from asset_mcp.providers import (
    BinanceProvider,
    IbkrProvider,
    LongbridgeProvider,
    ManualProvider,
    MoomooProvider,
    OkxProvider,
)
from asset_mcp.providers.base import AssetProvider


class AssetService:
    def __init__(self, config: AppConfig | None = None):
        self.config = config

    async def get_assets(
        self,
        source: str | None = None,
        accountId: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        assets = filter_assets(await self._fetch_all_assets(source=source), source, accountId, category)
        return [asset.to_dict() for asset in assets]

    async def get_net_worth(self) -> dict[str, Any]:
        return build_net_worth(await self._fetch_all_assets())

    async def get_asset_dashboard_data(self) -> dict[str, Any]:
        return build_dashboard_data(await self._fetch_all_assets())

    async def health_check_sources(self) -> dict[str, Any]:
        config = self._config()
        statuses = await asyncio.gather(
            *[provider.health_check() for provider in self._providers(config)],
            return_exceptions=True,
        )
        rows: list[AccountStatus] = []
        provider_errors: list[dict[str, str]] = []
        for result in statuses:
            if isinstance(result, Exception):
                provider_errors.append(
                    {"provider": result.__class__.__name__, "message": result.__class__.__name__}
                )
            else:
                rows.extend(result)
        return {
            "ok": all(row.ok for row in rows) and not provider_errors,
            "accounts": [row.to_dict() for row in rows],
            "providerErrors": provider_errors,
        }

    async def _fetch_all_assets(self, source: str | None = None) -> list[Asset]:
        config = self._config()
        results = await asyncio.gather(
            *[provider.fetch_assets() for provider in self._providers(config, source=source)],
            return_exceptions=True,
        )
        assets: list[Asset] = []
        errors: list[Exception] = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(result)
            else:
                assets.extend(result)
        if errors:
            names = ", ".join(error.__class__.__name__ for error in errors)
            raise RuntimeError(f"Failed to fetch one or more providers: {names}")
        return assets

    def _config(self) -> AppConfig:
        return self.config if self.config is not None else load_config()

    def _providers(self, config: AppConfig, source: str | None = None) -> list[AssetProvider]:
        providers: list[tuple[str, AssetProvider]] = [
            ("manual", ManualProvider(config)),
            ("binance", BinanceProvider(config)),
            ("okx", OkxProvider(config)),
            ("moomoo", MoomooProvider(config)),
            ("longbridge", LongbridgeProvider(config)),
            ("ibkr", IbkrProvider(config)),
        ]
        return [provider for provider_source, provider in providers if source in {None, provider_source}]
