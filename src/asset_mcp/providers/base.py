from __future__ import annotations

from abc import ABC, abstractmethod

from asset_mcp.models import AccountStatus, Asset


class AssetProvider(ABC):
    @abstractmethod
    async def fetch_assets(self) -> list[Asset]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> list[AccountStatus]:
        raise NotImplementedError
