from __future__ import annotations

from typing import Any

from asset_mcp.config import AppConfig, MoomooAccountConfig
from asset_mcp.domain.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider
from asset_mcp.providers.stdio import redirect_sdk_stdout

CASH_COLUMNS = {
    "hk_cash": "HKD",
    "us_cash": "USD",
    "cn_cash": "CNH",
    "jp_cash": "JPY",
    "sg_cash": "SGD",
    "au_cash": "AUD",
    "ca_cash": "CAD",
    "my_cash": "MYR",
}


class MoomooProvider(AssetProvider):
    def __init__(self, config: AppConfig):
        self.config = config

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        for account in self.config.moomooAccounts:
            if not account.enabled:
                continue
            assets.extend(self._fetch_account_assets(account))
        return assets

    async def health_check(self) -> list[AccountStatus]:
        statuses: list[AccountStatus] = []
        for account in self.config.moomooAccounts:
            if not account.enabled:
                statuses.append(AccountStatus("moomoo", account.id, account.label, False, True, "disabled"))
                continue
            try:
                self._check_account_connection(account)
                statuses.append(AccountStatus("moomoo", account.id, account.label, True, True, "ok"))
            except Exception as exc:  # noqa: BLE001
                statuses.append(
                    AccountStatus("moomoo", account.id, account.label, True, False, exc.__class__.__name__)
                )
        return statuses

    def _fetch_account_assets(self, account: MoomooAccountConfig) -> list[Asset]:
        with redirect_sdk_stdout():
            futu = self._import_futu()
            trd_ctx = futu.OpenSecTradeContext(
                filter_trdmarket=self._trd_market(futu, account.trdMarket),
                host=account.host,
                port=account.port,
                security_firm=self._security_firm(futu, account.securityFirm),
            )
            try:
                ret, accinfo = trd_ctx.accinfo_query(acc_id=account.accountId or 0)
                if ret != futu.RET_OK:
                    raise RuntimeError(f"moomoo accinfo_query failed: {accinfo}")
                ret, positions = trd_ctx.position_list_query(acc_id=account.accountId or 0)
                if ret != futu.RET_OK:
                    raise RuntimeError(f"moomoo position_list_query failed: {positions}")
                return self._assets_from_frames(account, accinfo, positions)
            finally:
                trd_ctx.close()

    def _check_account_connection(self, account: MoomooAccountConfig) -> None:
        with redirect_sdk_stdout():
            futu = self._import_futu()
            trd_ctx = futu.OpenSecTradeContext(
                filter_trdmarket=self._trd_market(futu, account.trdMarket),
                host=account.host,
                port=account.port,
                security_firm=self._security_firm(futu, account.securityFirm),
            )
            try:
                ret, accinfo = trd_ctx.accinfo_query(acc_id=account.accountId or 0)
                if ret != futu.RET_OK:
                    raise RuntimeError(f"moomoo accinfo_query failed: {accinfo}")
            finally:
                trd_ctx.close()

    def _assets_from_frames(self, account: MoomooAccountConfig, accinfo: Any, positions: Any) -> list[Asset]:
        now = utc_now_iso()
        assets: list[Asset] = []
        if len(accinfo) > 0:
            row = accinfo.iloc[0]
            assets.extend(self._cash_assets_from_accinfo(account, row, now))

        for _, row in positions.iterrows():
            code = str(row.get("code", "")).upper()
            qty = float(row.get("qty", row.get("can_sell_qty", 0)) or 0)
            market_value = float(row.get("market_val", row.get("market_value", 0)) or 0)
            currency = str(row.get("currency", "USD") or "USD").upper()
            if qty <= 0 and market_value <= 0:
                continue
            rate = self.config.rates.get(currency, 1.0 if currency == "USD" else 0.0)
            unit_price = (market_value / qty * rate) if qty > 0 else 0.0
            assets.append(
                Asset(
                    source="moomoo",
                    accountId=account.id,
                    accountLabel=account.label,
                    category="stock",
                    symbol=code,
                    name=str(row.get("stock_name", code) or code),
                    quantity=qty,
                    currency=currency,
                    unitPriceUsd=round(unit_price, 8),
                    valueUsd=round(market_value * rate, 8),
                    updatedAt=now,
                    rawSource="opend_positions",
                )
            )
        return assets

    def _cash_assets_from_accinfo(
        self,
        account: MoomooAccountConfig,
        row: Any,
        updated_at: str,
    ) -> list[Asset]:
        assets = [
            asset
            for column, currency in CASH_COLUMNS.items()
            if (asset := self._cash_asset(account, row.get(column, 0), currency, updated_at)) is not None
        ]
        if assets:
            return assets

        currency = str(row.get("currency", "USD") or "USD").upper()
        asset = self._cash_asset(account, row.get("cash", 0), currency, updated_at)
        return [asset] if asset is not None else []

    def _cash_asset(
        self,
        account: MoomooAccountConfig,
        quantity_raw: Any,
        currency: str,
        updated_at: str,
    ) -> Asset | None:
        try:
            quantity = float(quantity_raw or 0)
        except (TypeError, ValueError):
            return None
        if quantity <= 0:
            return None
        rate = self.config.rates.get(currency, 1.0 if currency == "USD" else 0.0)
        value = round(quantity * rate, 8)
        if value <= 0:
            return None
        return Asset(
            source="moomoo",
            accountId=account.id,
            accountLabel=account.label,
            category="cash",
            symbol=currency,
            name="Cash",
            quantity=quantity,
            currency=currency,
            unitPriceUsd=round(rate, 8),
            valueUsd=value,
            updatedAt=updated_at,
            rawSource="opend_accinfo_cash_by_currency",
        )

    def _import_futu(self):
        try:
            import moomoo as futu  # type: ignore
        except ImportError:
            try:
                import futu  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "Install moomoo support with: pip install moomoo-api"
                ) from exc
        try:
            getattr(futu.SecurityFirm, "FUTUSG")
            return futu
        except AttributeError:
            return futu

    def _trd_market(self, futu, value: str):
        if not hasattr(futu.TrdMarket, value.upper()):
            raise RuntimeError(f"Unsupported moomoo trdMarket: {value}")
        return getattr(futu.TrdMarket, value.upper())

    def _security_firm(self, futu, value: str):
        if not hasattr(futu.SecurityFirm, value):
            raise RuntimeError(f"Unsupported moomoo securityFirm: {value}")
        return getattr(futu.SecurityFirm, value)
