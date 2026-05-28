from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

AssetCategory = Literal["crypto", "stock", "cash", "manual"]
AssetSource = Literal["binance", "okx", "moomoo", "longbridge", "ibkr", "manual"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Asset:
    source: AssetSource
    accountId: str
    accountLabel: str
    category: AssetCategory
    symbol: str
    quantity: float
    currency: str
    unitPriceUsd: float
    valueUsd: float
    updatedAt: str
    name: str | None = None
    rawSource: str | None = None
    wallet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccountStatus:
    source: AssetSource
    accountId: str
    accountLabel: str
    enabled: bool
    ok: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sum_value_usd(assets: list[Asset]) -> float:
    return round(sum(asset.valueUsd for asset in assets), 8)
