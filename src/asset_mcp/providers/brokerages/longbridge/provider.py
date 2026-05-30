from __future__ import annotations

from decimal import Decimal
from typing import Any

from asset_mcp.config import AppConfig, LongbridgeAccountConfig
from asset_mcp.domain.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider
from asset_mcp.providers.stdio import redirect_sdk_stdout


class LongbridgeProvider(AssetProvider):
    def __init__(self, config: AppConfig):
        self.config = config

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        for account in self.config.longbridgeAccounts:
            if not account.enabled:
                continue
            assets.extend(self._fetch_account_assets(account))
        return assets

    async def health_check(self) -> list[AccountStatus]:
        statuses: list[AccountStatus] = []
        for account in self.config.longbridgeAccounts:
            if not account.enabled:
                statuses.append(
                    AccountStatus("longbridge", account.id, account.label, False, True, "disabled")
                )
                continue
            try:
                if not self._has_api_key_credentials(account):
                    statuses.append(
                        AccountStatus(
                            "longbridge",
                            account.id,
                            account.label,
                            True,
                            False,
                            "missing credentials",
                        )
                    )
                    continue
                with redirect_sdk_stdout():
                    sdk = self._import_sdk()
                    trade_ctx = self._trade_context(sdk, account)
                    try:
                        trade_ctx.account_balance()
                    finally:
                        self._close_context(trade_ctx)
                statuses.append(
                    AccountStatus("longbridge", account.id, account.label, True, True, "ok")
                )
            except Exception as exc:  # noqa: BLE001
                statuses.append(
                    AccountStatus(
                        "longbridge",
                        account.id,
                        account.label,
                        True,
                        False,
                        exc.__class__.__name__,
                    )
                )
        return statuses

    def _fetch_account_assets(self, account: LongbridgeAccountConfig) -> list[Asset]:
        with redirect_sdk_stdout():
            sdk = self._import_sdk()
            trade_ctx = self._trade_context(sdk, account)
            quote_ctx = None
            try:
                balances = trade_ctx.account_balance()
                positions = trade_ctx.stock_positions()
                symbols = self._position_symbols(positions)
                quote_prices: dict[str, float] = {}
                if symbols:
                    quote_ctx = self._quote_context(sdk, account)
                    quote_prices = self._quote_prices(quote_ctx, symbols)
                return self._assets_from_account_data(account, balances, positions, quote_prices)
            finally:
                self._close_context(trade_ctx)
                if quote_ctx is not None:
                    self._close_context(quote_ctx)

    def _assets_from_account_data(
        self,
        account: LongbridgeAccountConfig,
        balances: Any,
        positions: Any,
        quote_prices: dict[str, float] | None = None,
    ) -> list[Asset]:
        now = utc_now_iso()
        return [
            *self._cash_assets(account, balances, now),
            *self._stock_assets(account, positions, quote_prices or {}, now),
        ]

    def _cash_assets(
        self,
        account: LongbridgeAccountConfig,
        balances: Any,
        updated_at: str,
    ) -> list[Asset]:
        assets: list[Asset] = []
        for balance in self._response_list(balances):
            balance_assets: list[Asset] = []
            for cash_info in self._iter_cash_infos(balance):
                currency = self._str_value(cash_info, "currency").upper()
                quantity = (
                    self._float_value(cash_info, "available_cash")
                    + self._float_value(cash_info, "frozen_cash")
                    + self._float_value(cash_info, "settling_cash")
                )
                asset = self._cash_asset(
                    account,
                    currency,
                    quantity,
                    updated_at,
                    "account_cash_info",
                )
                if asset is not None:
                    balance_assets.append(asset)

            if balance_assets:
                assets.extend(balance_assets)
                continue

            currency = self._str_value(balance, "currency").upper()
            total_cash = self._float_value(balance, "total_cash")
            asset = self._cash_asset(account, currency, total_cash, updated_at, "account_balance")
            if asset is not None:
                assets.append(asset)
        return assets

    def _stock_assets(
        self,
        account: LongbridgeAccountConfig,
        positions: Any,
        quote_prices: dict[str, float],
        updated_at: str,
    ) -> list[Asset]:
        assets: list[Asset] = []
        for group in self._response_list(positions):
            account_channel = self._str_value(group, "account_channel") or None
            stock_infos = self._value(group, "positions", "stock_info", "stockInfo") or [group]
            for stock in stock_infos:
                symbol = self._str_value(stock, "symbol").upper()
                quantity = self._float_value(stock, "quantity")
                currency = self._str_value(stock, "currency").upper()
                if not symbol or quantity <= 0:
                    continue

                price = quote_prices.get(symbol) or self._float_value(stock, "cost_price")
                rate = self._usd_rate(currency)
                value_usd = round(quantity * price * rate, 8)
                if value_usd <= 0:
                    continue

                assets.append(
                    Asset(
                        source="longbridge",
                        accountId=account.id,
                        accountLabel=account.label,
                        category="stock",
                        symbol=symbol,
                        name=self._str_value(stock, "symbol_name") or symbol,
                        quantity=quantity,
                        currency=currency,
                        unitPriceUsd=round(price * rate, 8),
                        valueUsd=value_usd,
                        updatedAt=updated_at,
                        rawSource="stock_positions_quote"
                        if symbol in quote_prices
                        else "stock_positions_cost_price",
                        wallet=account_channel,
                    )
                )
        return assets

    def _position_symbols(self, positions: Any) -> list[str]:
        symbols: list[str] = []
        for group in self._response_list(positions):
            stock_infos = self._value(group, "positions", "stock_info", "stockInfo") or [group]
            for stock in stock_infos:
                symbol = self._str_value(stock, "symbol").upper()
                if symbol:
                    symbols.append(symbol)
        return symbols

    def _quote_prices(self, quote_ctx: Any, symbols: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for chunk in _chunks(symbols, 500):
            try:
                quotes = quote_ctx.quote(chunk)
            except Exception:  # noqa: BLE001
                continue
            for quote in self._response_list(quotes):
                symbol = self._str_value(quote, "symbol").upper()
                last_done = self._float_value(quote, "last_done")
                if symbol and last_done > 0:
                    prices[symbol] = last_done
        return prices

    def _cash_asset(
        self,
        account: LongbridgeAccountConfig,
        currency: str,
        quantity: float,
        updated_at: str,
        raw_source: str,
    ) -> Asset | None:
        if not currency or quantity <= 0:
            return None
        rate = self._usd_rate(currency)
        value_usd = round(quantity * rate, 8)
        if value_usd <= 0:
            return None
        return Asset(
            source="longbridge",
            accountId=account.id,
            accountLabel=account.label,
            category="cash",
            symbol=currency,
            name="Cash",
            quantity=quantity,
            currency=currency,
            unitPriceUsd=round(rate, 8),
            valueUsd=value_usd,
            updatedAt=updated_at,
            rawSource=raw_source,
        )

    def _trade_context(self, sdk: Any, account: LongbridgeAccountConfig) -> Any:
        return sdk.TradeContext(self._sdk_config(sdk, account))

    def _quote_context(self, sdk: Any, account: LongbridgeAccountConfig) -> Any:
        return sdk.QuoteContext(self._sdk_config(sdk, account))

    def _sdk_config(self, sdk: Any, account: LongbridgeAccountConfig) -> Any:
        if not self._has_api_key_credentials(account):
            raise RuntimeError("missing longbridge API key credentials")
        return sdk.Config.from_apikey(account.appKey, account.appSecret, account.accessToken)

    def _has_api_key_credentials(self, account: LongbridgeAccountConfig) -> bool:
        return bool(account.appKey and account.appSecret and account.accessToken)

    def _import_sdk(self) -> Any:
        try:
            import longbridge.openapi as sdk  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Install Longbridge support with: pip install 'asset-mcp[longbridge]'"
            ) from exc
        return sdk

    def _iter_cash_infos(self, balance: Any) -> list[Any]:
        value = self._value(balance, "cash_infos", "cashInfos")
        if value is None:
            return []
        return list(value)

    def _response_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list | tuple):
            return list(value)
        if isinstance(value, dict):
            data = value.get("data", value)
            if isinstance(data, dict):
                rows = (
                    data.get("list")
                    or data.get("channels")
                    or data.get("positions")
                    or data.get("stock_info")
                    or data.get("stockInfo")
                )
                if rows is not None:
                    return list(rows)
            if isinstance(data, list):
                return data
        channels = self._value(value, "channels")
        if channels is not None:
            return list(channels)
        return list(value) if hasattr(value, "__iter__") and not isinstance(value, str) else [value]

    def _value(self, obj: Any, *names: str) -> Any:
        for name in names:
            if isinstance(obj, dict) and name in obj:
                return obj[name]
            if hasattr(obj, name):
                return getattr(obj, name)
        return None

    def _str_value(self, obj: Any, *names: str) -> str:
        value = self._value(obj, *names)
        return "" if value is None else str(value)

    def _float_value(self, obj: Any, *names: str) -> float:
        value = self._value(obj, *names)
        if value is None or value == "":
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _usd_rate(self, currency: str) -> float:
        return self.config.rates.get(currency, 1.0 if currency == "USD" else 0.0)

    def _close_context(self, ctx: Any) -> None:
        close = getattr(ctx, "close", None)
        if callable(close):
            close()


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
