from __future__ import annotations

from collections.abc import Callable

from asset_mcp.config import AppConfig
from asset_mcp.providers.base import AssetProvider
from asset_mcp.providers.brokerages.ibkr import IbkrProvider
from asset_mcp.providers.brokerages.longbridge import LongbridgeProvider
from asset_mcp.providers.brokerages.moomoo import MoomooProvider
from asset_mcp.providers.exchanges.binance import BinanceProvider
from asset_mcp.providers.exchanges.okx import OkxProvider
from asset_mcp.providers.manual import ManualProvider
from asset_mcp.providers.onchain import OnchainProvider

ProviderFactory = Callable[[AppConfig], AssetProvider]

PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "manual": ManualProvider,
    "binance": BinanceProvider,
    "okx": OkxProvider,
    "moomoo": MoomooProvider,
    "longbridge": LongbridgeProvider,
    "ibkr": IbkrProvider,
    "onchain": OnchainProvider,
}


def build_provider_entries(
    config: AppConfig,
    source: str | None = None,
) -> list[tuple[str, AssetProvider]]:
    return [
        (provider_source, factory(config))
        for provider_source, factory in PROVIDER_FACTORIES.items()
        if source in {None, provider_source}
    ]
