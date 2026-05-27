from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx

from asset_mcp.config import AppConfig, BinanceAccountConfig
from asset_mcp.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider

BINANCE_PRODUCTION_URL = "https://api.binance.com"
BINANCE_PAPI_URL = "https://papi.binance.com"
BINANCE_FAPI_URL = "https://fapi.binance.com"
BINANCE_DAPI_URL = "https://dapi.binance.com"
STABLE_USD_SYMBOLS = {
    "USD",
    "USDT",
    "USDC",
    "BUSD",
    "FDUSD",
    "TUSD",
    "DAI",
    "USDP",
    "USD1",
    "BFUSD",
    "USDE",
}


@dataclass
class _BinanceDiagnostics:
    ok: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    missing_prices: set[str] = field(default_factory=set)

    def message(self) -> str:
        parts = []
        if self.ok:
            parts.append(f"covered: {', '.join(self.ok)}")
        if self.failed:
            parts.append(f"failed optional: {', '.join(self.failed)}")
        if self.missing_prices:
            parts.append(f"missing prices: {', '.join(sorted(self.missing_prices))}")
        return "; ".join(parts) if parts else "ok"


class BinanceProvider(AssetProvider):
    def __init__(self, config: AppConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self.client = client

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        async with self._client() as client:
            for account in self.config.binanceAccounts:
                if not account.enabled:
                    continue
                account_assets, _diagnostics = await self._fetch_account_assets(client, account)
                assets.extend(account_assets)
        return assets

    async def health_check(self) -> list[AccountStatus]:
        statuses: list[AccountStatus] = []
        async with self._client() as client:
            for account in self.config.binanceAccounts:
                if not account.enabled:
                    statuses.append(
                        AccountStatus("binance", account.id, account.label, False, True, "disabled")
                    )
                    continue
                if not account.apiKey or not account.apiSecret:
                    statuses.append(
                        AccountStatus(
                            "binance", account.id, account.label, True, False, "missing credentials"
                        )
                    )
                    continue
                try:
                    _assets, diagnostics = await self._fetch_account_assets(client, account)
                    statuses.append(
                        AccountStatus(
                            "binance",
                            account.id,
                            account.label,
                            True,
                            True,
                            diagnostics.message(),
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    statuses.append(
                        AccountStatus(
                            "binance",
                            account.id,
                            account.label,
                            True,
                            False,
                            _safe_error(exc),
                        )
                    )
        return statuses

    async def _fetch_account_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
    ) -> tuple[list[Asset], _BinanceDiagnostics]:
        diagnostics = _BinanceDiagnostics()
        account_info = await self._signed_get(client, account, _base_url(account), "/api/v3/account", {})
        diagnostics.ok.append("spot")
        prices = await self._price_map(client, account)
        assets = self._assets_from_spot_account(account, account_info, prices, diagnostics)

        wallet_overview = await self._optional(
            diagnostics,
            "wallet_balance",
            lambda: self._wallet_overview(client, account),
        )
        portfolio_assets = await self._optional(
            diagnostics,
            "portfolio_margin",
            lambda: self._portfolio_margin_assets(client, account, prices),
        )
        portfolio_margin_available = portfolio_assets is not None
        if portfolio_assets:
            assets.extend(portfolio_assets)

        funding_assets = await self._optional(
            diagnostics,
            "funding",
            lambda: self._funding_wallet_assets(client, account, prices, diagnostics),
        )
        if funding_assets:
            assets.extend(funding_assets)

        simple_earn_account = await self._optional(
            diagnostics,
            "simple_earn_account",
            lambda: self._simple_earn_account(client, account),
        )
        earn_assets = []
        flexible_assets = await self._optional(
            diagnostics,
            "earn_flexible",
            lambda: self._simple_earn_flexible_assets(client, account, prices, diagnostics),
        )
        if flexible_assets:
            earn_assets.extend(flexible_assets)
        locked_assets = await self._optional(
            diagnostics,
            "earn_locked",
            lambda: self._simple_earn_locked_assets(client, account, prices, diagnostics),
        )
        if locked_assets:
            earn_assets.extend(locked_assets)
        if earn_assets:
            assets.extend(earn_assets)
        elif simple_earn_account is not None:
            assets.extend(self._assets_from_simple_earn_account(account, simple_earn_account))

        rwusd_asset = await self._optional(
            diagnostics,
            "rwusd",
            lambda: self._rwusd_asset(client, account, prices, diagnostics),
        )
        if rwusd_asset and not _has_symbol(assets, "RWUSD"):
            assets.extend(rwusd_asset)
        bfusd_asset = await self._optional(
            diagnostics,
            "bfusd",
            lambda: self._bfusd_asset(client, account, prices, diagnostics),
        )
        if bfusd_asset and not _has_symbol(assets, "BFUSD"):
            assets.extend(bfusd_asset)

        if not portfolio_margin_available:
            assets.extend(
                await self._optional(
                    diagnostics,
                    "um_futures",
                    lambda: self._futures_assets(
                        client,
                        account,
                        BINANCE_FAPI_URL,
                        "/fapi/v3/balance",
                        "um_futures",
                        "um_futures_balance",
                        prices,
                        diagnostics,
                    ),
                )
                or []
            )
            assets.extend(
                await self._optional(
                    diagnostics,
                    "cm_futures",
                    lambda: self._futures_assets(
                        client,
                        account,
                        BINANCE_DAPI_URL,
                        "/dapi/v1/balance",
                        "cm_futures",
                        "cm_futures_balance",
                        prices,
                        diagnostics,
                    ),
                )
                or []
            )
            assets.extend(
                await self._optional(
                    diagnostics,
                    "cross_margin",
                    lambda: self._cross_margin_assets(client, account, prices, diagnostics),
                )
                or []
            )
            assets.extend(
                await self._optional(
                    diagnostics,
                    "isolated_margin",
                    lambda: self._isolated_margin_assets(client, account, prices, diagnostics),
                )
                or []
            )

        if wallet_overview:
            covered_wallets = {asset.wallet for asset in assets if asset.wallet}
            assets.extend(self._wallet_overview_estimates(account, wallet_overview, covered_wallets))

        return assets, diagnostics

    async def _optional(self, diagnostics: _BinanceDiagnostics, name: str, call):
        try:
            result = await call()
        except Exception as exc:  # noqa: BLE001
            diagnostics.failed.append(f"{name} ({_safe_error(exc)})")
            return None
        diagnostics.ok.append(name)
        return result

    def _assets_from_spot_account(
        self,
        account: BinanceAccountConfig,
        account_info: dict[str, Any],
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics | None = None,
    ) -> list[Asset]:
        assets: list[Asset] = []
        for balance in account_info.get("balances", []):
            symbol = str(balance.get("asset", "")).upper()
            quantity = _float(balance.get("free")) + _float(balance.get("locked"))
            asset = _asset_from_quantity(
                account,
                symbol,
                quantity,
                prices,
                "spot_account",
                "spot",
                diagnostics,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    def _assets_from_account(
        self,
        account: BinanceAccountConfig,
        account_info: dict,
        prices: dict[str, float],
    ) -> list[Asset]:
        return self._assets_from_spot_account(account, account_info, prices)

    async def _portfolio_margin_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
    ) -> list[Asset]:
        data = await self._signed_get(client, account, BINANCE_PAPI_URL, "/papi/v1/balance", {})
        rows = data if isinstance(data, list) else [data]
        assets = []
        for row in rows:
            asset = _asset_from_quantity(
                account,
                str(row.get("asset", "")).upper(),
                _float(row.get("totalWalletBalance")),
                prices,
                "portfolio_margin_balance",
                "portfolio_margin",
                None,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _wallet_overview(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
    ) -> list[dict[str, Any]]:
        data = await self._signed_get(
            client,
            account,
            _base_url(account),
            "/sapi/v1/asset/wallet/balance",
            {"quoteAsset": "USDT"},
        )
        return data if isinstance(data, list) else []

    def _wallet_overview_estimates(
        self,
        account: BinanceAccountConfig,
        rows: list[dict[str, Any]],
        covered_wallets: set[str],
    ) -> list[Asset]:
        now = utc_now_iso()
        assets: list[Asset] = []
        for row in rows:
            wallet_name = str(row.get("walletName") or "Other")
            wallet = _wallet_slug(wallet_name)
            if wallet in covered_wallets:
                continue
            quantity = _float(row.get("balance"))
            if quantity <= 0:
                continue
            assets.append(
                Asset(
                    source="binance",
                    accountId=account.id,
                    accountLabel=account.label,
                    category="crypto",
                    symbol="USDT",
                    quantity=quantity,
                    currency="USDT",
                    unitPriceUsd=1.0,
                    valueUsd=round(quantity, 8),
                    updatedAt=now,
                    name=f"{wallet_name} wallet estimate",
                    rawSource="wallet_balance",
                    wallet=wallet,
                )
            )
        return assets

    async def _funding_wallet_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        data = await self._signed_post(
            client,
            account,
            _base_url(account),
            "/sapi/v1/asset/get-funding-asset",
            {"needBtcValuation": "true"},
        )
        assets = []
        for row in data if isinstance(data, list) else []:
            quantity = (
                _float(row.get("free"))
                + _float(row.get("locked"))
                + _float(row.get("freeze"))
                + _float(row.get("withdrawing"))
            )
            asset = _asset_from_quantity(
                account,
                str(row.get("asset", "")).upper(),
                quantity,
                prices,
                "funding_wallet",
                "funding",
                diagnostics,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _simple_earn_account(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
    ) -> dict[str, Any]:
        data = await self._signed_get(
            client,
            account,
            _base_url(account),
            "/sapi/v1/simple-earn/account",
            {},
        )
        return data if isinstance(data, dict) else {}

    def _assets_from_simple_earn_account(
        self,
        account: BinanceAccountConfig,
        data: dict[str, Any],
    ) -> list[Asset]:
        total_usdt = _float(data.get("totalAmountInUSDT"))
        if total_usdt <= 0:
            return []
        return [
            Asset(
                source="binance",
                accountId=account.id,
                accountLabel=account.label,
                category="crypto",
                symbol="USDT",
                quantity=total_usdt,
                currency="USDT",
                unitPriceUsd=1.0,
                valueUsd=round(total_usdt, 8),
                updatedAt=utc_now_iso(),
                name="Simple Earn total estimate",
                rawSource="simple_earn_account",
                wallet="earn",
            )
        ]

    async def _simple_earn_flexible_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        rows = await self._paged_rows(
            client, account, "/sapi/v1/simple-earn/flexible/position"
        )
        assets = []
        for row in rows:
            asset = _asset_from_quantity(
                account,
                str(row.get("asset", "")).upper(),
                _float(row.get("totalAmount")),
                prices,
                "simple_earn_flexible_position",
                "earn_flexible",
                diagnostics,
                name=str(row.get("productId") or "") or None,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _simple_earn_locked_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        rows = await self._paged_rows(client, account, "/sapi/v1/simple-earn/locked/position")
        assets = []
        for row in rows:
            asset = _asset_from_quantity(
                account,
                str(row.get("asset", "")).upper(),
                _float(row.get("amount")) + _float(row.get("redeemingAmt")),
                prices,
                "simple_earn_locked_position",
                "earn_locked",
                diagnostics,
                name=str(row.get("projectId") or "") or None,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _rwusd_asset(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        data = await self._signed_get(client, account, _base_url(account), "/sapi/v1/rwusd/account", {})
        asset = _asset_from_quantity(
            account,
            "RWUSD",
            _float(data.get("rwusdAmount")) if isinstance(data, dict) else 0.0,
            prices,
            "rwusd_account",
            "rwusd",
            diagnostics,
        )
        return [asset] if asset is not None else []

    async def _bfusd_asset(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        data = await self._signed_get(client, account, _base_url(account), "/sapi/v1/bfusd/account", {})
        asset = _asset_from_quantity(
            account,
            "BFUSD",
            _float(data.get("bfusdAmount")) if isinstance(data, dict) else 0.0,
            prices,
            "bfusd_account",
            "bfusd",
            diagnostics,
        )
        return [asset] if asset is not None else []

    async def _futures_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        base_url: str,
        path: str,
        wallet: str,
        raw_source: str,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        data = await self._signed_get(client, account, base_url, path, {})
        assets = []
        for row in data if isinstance(data, list) else []:
            asset = _asset_from_quantity(
                account,
                str(row.get("asset", "")).upper(),
                _float(row.get("balance")),
                prices,
                raw_source,
                wallet,
                diagnostics,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _cross_margin_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        data = await self._signed_get(
            client, account, _base_url(account), "/sapi/v1/margin/account", {}
        )
        assets = []
        for row in data.get("userAssets", []) if isinstance(data, dict) else []:
            asset = _asset_from_quantity(
                account,
                str(row.get("asset", "")).upper(),
                _float(row.get("netAsset")),
                prices,
                "cross_margin_account",
                "cross_margin",
                diagnostics,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _isolated_margin_assets(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        prices: dict[str, float],
        diagnostics: _BinanceDiagnostics,
    ) -> list[Asset]:
        data = await self._signed_get(
            client,
            account,
            _base_url(account),
            "/sapi/v1/margin/isolated/account",
            {},
        )
        assets = []
        for market in data.get("assets", []) if isinstance(data, dict) else []:
            market_name = str(market.get("symbol") or "") or None
            for side in ("baseAsset", "quoteAsset"):
                row = market.get(side) or {}
                asset = _asset_from_quantity(
                    account,
                    str(row.get("asset", "")).upper(),
                    _float(row.get("netAsset")),
                    prices,
                    "isolated_margin_account",
                    "isolated_margin",
                    diagnostics,
                    name=market_name,
                )
                if asset is not None:
                    assets.append(asset)
        return assets

    async def _paged_rows(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        path: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        current = 1
        size = 100
        while True:
            data = await self._signed_get(
                client,
                account,
                _base_url(account),
                path,
                {"current": current, "size": size},
            )
            page_rows = data.get("rows", []) if isinstance(data, dict) else []
            rows.extend(page_rows)
            total = int(data.get("total", len(rows)) or len(rows)) if isinstance(data, dict) else len(rows)
            if not page_rows or len(rows) >= total:
                break
            current += 1
        return rows

    async def _price_map(
        self, client: httpx.AsyncClient, account: BinanceAccountConfig
    ) -> dict[str, float]:
        response = await client.get(f"{_base_url(account)}/api/v3/ticker/price")
        response.raise_for_status()
        prices: dict[str, float] = {}
        for row in response.json():
            pair = str(row.get("symbol", "")).upper()
            price = _float(row.get("price"))
            if pair.endswith("USDT"):
                prices[pair.removesuffix("USDT")] = price
            elif pair.endswith("USDC"):
                prices.setdefault(pair.removesuffix("USDC"), price)
        for symbol in STABLE_USD_SYMBOLS:
            prices[symbol] = 1.0
        return prices

    async def _signed_get(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        base_url: str,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        return await self._signed_request("GET", client, account, base_url, path, params)

    async def _signed_post(
        self,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        base_url: str,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        return await self._signed_request("POST", client, account, base_url, path, params)

    async def _signed_request(
        self,
        method: str,
        client: httpx.AsyncClient,
        account: BinanceAccountConfig,
        base_url: str,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        signed_params = dict(params)
        signed_params["timestamp"] = int(time.time() * 1000)
        query = urlencode(signed_params)
        signature = hmac.new(account.apiSecret.encode(), query.encode(), hashlib.sha256).hexdigest()
        signed_params["signature"] = signature
        request = client.get if method == "GET" else client.post
        response = await request(
            f"{base_url}{path}",
            params=signed_params,
            headers={"X-MBX-APIKEY": account.apiKey},
        )
        response.raise_for_status()
        return response.json()

    def _client(self):
        if self.client is not None:
            return _NullAsyncContext(self.client)
        return httpx.AsyncClient(timeout=20)


def _asset_from_quantity(
    account: BinanceAccountConfig,
    symbol: str,
    quantity: float,
    prices: dict[str, float],
    raw_source: str,
    wallet: str,
    diagnostics: _BinanceDiagnostics | None,
    name: str | None = None,
) -> Asset | None:
    symbol = symbol.upper()
    if not symbol or quantity <= 0:
        return None
    unit_price_usd = _price_for_symbol(symbol, prices)
    if unit_price_usd <= 0:
        if diagnostics is not None:
            diagnostics.missing_prices.add(symbol)
        return None
    value_usd = round(quantity * unit_price_usd, 8)
    if value_usd <= 0:
        return None
    return Asset(
        source="binance",
        accountId=account.id,
        accountLabel=account.label,
        category="crypto",
        symbol=symbol,
        quantity=quantity,
        currency=symbol,
        unitPriceUsd=round(unit_price_usd, 8),
        valueUsd=value_usd,
        updatedAt=utc_now_iso(),
        name=name,
        rawSource=raw_source,
        wallet=wallet,
    )


def _base_url(_account: BinanceAccountConfig) -> str:
    return BINANCE_PRODUCTION_URL


def _price_for_symbol(symbol: str, prices: dict[str, float]) -> float:
    if symbol in STABLE_USD_SYMBOLS:
        return 1.0
    return float(prices.get(symbol, 0.0))


def _has_symbol(assets: list[Asset], symbol: str) -> bool:
    return any(asset.symbol == symbol for asset in assets)


def _wallet_slug(wallet_name: str) -> str:
    normalized = wallet_name.strip().lower()
    known = {
        "spot": "spot",
        "funding": "funding",
        "cross margin": "cross_margin",
        "cross margin (pm)": "portfolio_margin",
        "isolated margin": "isolated_margin",
        "usdⓈ-m futures": "um_futures",
        "usds-m futures": "um_futures",
        "coin-m futures": "cm_futures",
        "earn": "earn",
        "options": "options",
        "trading bots": "trading_bots",
        "copy trading": "copy_trading",
    }
    if normalized in known:
        return known[normalized]
    return "".join(char if char.isalnum() else "_" for char in normalized).strip("_") or "other"


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            payload = exc.response.json()
        except ValueError:
            return f"HTTP {status}"
        code = payload.get("code")
        msg = str(payload.get("msg") or "").strip()
        if code is not None and msg:
            return f"HTTP {status} Binance {code}: {msg[:120]}"
        return f"HTTP {status}"
    return exc.__class__.__name__


class _NullAsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False
