from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone

import httpx

from asset_mcp.config import AppConfig, OkxAccountConfig
from asset_mcp.domain.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider

OKX_STABLE_USD_SYMBOLS = {"USD", "USDT", "USDC", "DAI"}


class OkxProvider(AssetProvider):
    def __init__(self, config: AppConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self.client = client

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        async with self._client() as client:
            for account in self.config.okxAccounts:
                if not account.enabled:
                    continue
                account_balances = await self._signed_get(client, account, "/api/v5/account/balance")
                funding_balances = await self._signed_get(client, account, "/api/v5/asset/balances")
                prices = await self._price_map(client, account)
                assets.extend(
                    self._assets_from_balances(account, account_balances, funding_balances, prices)
                )
        return assets

    async def health_check(self) -> list[AccountStatus]:
        statuses: list[AccountStatus] = []
        async with self._client() as client:
            for account in self.config.okxAccounts:
                if not account.enabled:
                    statuses.append(AccountStatus("okx", account.id, account.label, False, True, "disabled"))
                    continue
                if not account.apiKey or not account.apiSecret or not account.passphrase:
                    statuses.append(
                        AccountStatus("okx", account.id, account.label, True, False, "missing credentials")
                    )
                    continue
                try:
                    await self._signed_get(client, account, "/api/v5/account/balance")
                    statuses.append(AccountStatus("okx", account.id, account.label, True, True, "ok"))
                except Exception as exc:  # noqa: BLE001
                    statuses.append(
                        AccountStatus("okx", account.id, account.label, True, False, exc.__class__.__name__)
                    )
        return statuses

    def _assets_from_balances(
        self,
        account: OkxAccountConfig,
        account_balances: dict,
        funding_balances: dict,
        prices: dict[str, float],
    ) -> list[Asset]:
        now = utc_now_iso()
        assets: list[Asset] = []
        for item in account_balances.get("data", []):
            for detail in item.get("details", []):
                currency = str(detail.get("ccy", "")).upper()
                quantity = float(detail.get("cashBal") or detail.get("eq") or 0)
                asset = self._asset_from_quantity(
                    account,
                    currency,
                    quantity,
                    prices,
                    now,
                    "account_balance",
                    "trading",
                )
                if asset is not None:
                    assets.append(asset)
        for item in funding_balances.get("data", []):
            currency = str(item.get("ccy", "")).upper()
            quantity = float(item.get("bal") or item.get("availBal") or 0)
            asset = self._asset_from_quantity(
                account,
                currency,
                quantity,
                prices,
                now,
                "funding_balance",
                "funding",
            )
            if asset is not None:
                assets.append(asset)

        return assets

    def _asset_from_quantity(
        self,
        account: OkxAccountConfig,
        currency: str,
        quantity: float,
        prices: dict[str, float],
        updated_at: str,
        raw_source: str,
        wallet: str,
    ) -> Asset | None:
        if quantity <= 0:
            return None
        unit_price_usd = 1.0 if currency in OKX_STABLE_USD_SYMBOLS else prices.get(currency, 0.0)
        value_usd = round(quantity * unit_price_usd, 8)
        if value_usd <= 0:
            return None
        return Asset(
            source="okx",
            accountId=account.id,
            accountLabel=account.label,
            category="crypto",
            symbol=currency,
            quantity=quantity,
            currency=currency,
            unitPriceUsd=round(unit_price_usd, 8),
            valueUsd=value_usd,
            updatedAt=updated_at,
            rawSource=raw_source,
            wallet=wallet,
        )

    async def _price_map(self, client: httpx.AsyncClient, account: OkxAccountConfig) -> dict[str, float]:
        response = await client.get(f"{account.domain}/api/v5/market/tickers", params={"instType": "SPOT"})
        response.raise_for_status()
        prices: dict[str, float] = {symbol: 1.0 for symbol in OKX_STABLE_USD_SYMBOLS}
        for row in response.json().get("data", []):
            inst_id = str(row.get("instId", "")).upper()
            last = float(row.get("last") or 0)
            if inst_id.endswith("-USDT"):
                prices[inst_id.removesuffix("-USDT")] = last
            elif inst_id.endswith("-USDC"):
                prices.setdefault(inst_id.removesuffix("-USDC"), last)
        return prices

    async def _signed_get(
        self,
        client: httpx.AsyncClient,
        account: OkxAccountConfig,
        path: str,
    ) -> dict:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        message = f"{timestamp}GET{path}"
        signature = base64.b64encode(
            hmac.new(account.apiSecret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()
        response = await client.get(
            f"{account.domain}{path}",
            headers={
                "OK-ACCESS-KEY": account.apiKey,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": account.passphrase,
            },
        )
        response.raise_for_status()
        return response.json()

    def _client(self):
        if self.client is not None:
            return _NullAsyncContext(self.client)
        return httpx.AsyncClient(timeout=20)


class _NullAsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False
