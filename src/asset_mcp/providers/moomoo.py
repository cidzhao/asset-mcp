from __future__ import annotations

from typing import Any

from asset_mcp.config import AppConfig, MoomooAccountConfig
from asset_mcp.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider


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
                raise RuntimeError("moomoo accinfo_query failed")
            ret, positions = trd_ctx.position_list_query(acc_id=account.accountId or 0)
            if ret != futu.RET_OK:
                raise RuntimeError("moomoo position_list_query failed")
            return self._assets_from_frames(account, accinfo, positions)
        finally:
            trd_ctx.close()

    def _check_account_connection(self, account: MoomooAccountConfig) -> None:
        futu = self._import_futu()
        trd_ctx = futu.OpenSecTradeContext(
            filter_trdmarket=self._trd_market(futu, account.trdMarket),
            host=account.host,
            port=account.port,
            security_firm=self._security_firm(futu, account.securityFirm),
        )
        try:
            ret, _accinfo = trd_ctx.accinfo_query(acc_id=account.accountId or 0)
            if ret != futu.RET_OK:
                raise RuntimeError("moomoo accinfo_query failed")
        finally:
            trd_ctx.close()

    def _assets_from_frames(self, account: MoomooAccountConfig, accinfo: Any, positions: Any) -> list[Asset]:
        now = utc_now_iso()
        assets: list[Asset] = []
        if len(accinfo) > 0:
            row = accinfo.iloc[0]
            cash = float(row.get("cash", 0) or 0)
            currency = str(row.get("currency", "USD") or "USD").upper()
            if cash > 0:
                rate = self.config.rates.get(currency, 1.0 if currency == "USD" else 0.0)
                value = round(cash * rate, 8)
                assets.append(
                    Asset(
                        source="moomoo",
                        accountId=account.id,
                        accountLabel=account.label,
                        category="cash",
                        symbol=currency,
                        name="Cash",
                        quantity=cash,
                        currency=currency,
                        unitPriceUsd=round(rate, 8),
                        valueUsd=value,
                        updatedAt=now,
                        rawSource="opend_accinfo",
                    )
                )

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

    def _import_futu(self):
        try:
            import futu  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Install moomoo support with: uv sync --extra moomoo") from exc
        return futu

    def _trd_market(self, futu, value: str):
        return getattr(futu.TrdMarket, value.upper(), futu.TrdMarket.US)

    def _security_firm(self, futu, value: str):
        return getattr(futu.SecurityFirm, value, futu.SecurityFirm.FUTUSECURITIES)
