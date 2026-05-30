from __future__ import annotations

from asset_mcp.config import AppConfig, ManualAccountConfig
from asset_mcp.domain.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider

VALID_MANUAL_CATEGORIES = {"cash", "manual", "stock", "crypto"}


class ManualProvider(AssetProvider):
    def __init__(self, config: AppConfig):
        self.config = config

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        now = utc_now_iso()
        for account in self.config.manualAccounts:
            if not account.enabled:
                continue
            category = account.category if account.category in VALID_MANUAL_CATEGORIES else "manual"
            for item in account.assets:
                unit_price_usd = self._rate_for(item.currency)
                value_usd = round(item.quantity * unit_price_usd, 8)
                assets.append(
                    Asset(
                        source="manual",
                        accountId=account.id,
                        accountLabel=account.label,
                        category=category,  # type: ignore[arg-type]
                        symbol=item.symbol.upper(),
                        name=item.name,
                        quantity=item.quantity,
                        currency=item.currency.upper(),
                        unitPriceUsd=round(unit_price_usd, 8),
                        valueUsd=value_usd,
                        updatedAt=now,
                        rawSource="config",
                    )
                )
        return assets

    async def health_check(self) -> list[AccountStatus]:
        return [self._status(account) for account in self.config.manualAccounts]

    def _status(self, account: ManualAccountConfig) -> AccountStatus:
        if not account.enabled:
            return AccountStatus("manual", account.id, account.label, False, True, "disabled")
        missing_rates = [
            asset.currency
            for asset in account.assets
            if asset.currency.upper() not in self.config.rates
        ]
        if missing_rates:
            return AccountStatus(
                "manual",
                account.id,
                account.label,
                True,
                False,
                f"missing rates for: {', '.join(sorted(set(missing_rates)))}",
            )
        return AccountStatus("manual", account.id, account.label, True, True, "ok")

    def _rate_for(self, currency: str) -> float:
        rate = self.config.rates.get(currency.upper())
        if rate is None:
            raise ValueError(f"Missing USD rate for currency '{currency}'.")
        return rate
