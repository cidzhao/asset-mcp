from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from asset_mcp import __version__
from asset_mcp.config import AppConfig, IbkrAccountConfig
from asset_mcp.domain.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider

TRANSIENT_FLEX_ERROR_CODES = {
    "1001",
    "1003",
    "1004",
    "1005",
    "1006",
    "1007",
    "1008",
    "1009",
    "1019",
    "1021",
}


class IbkrProvider(AssetProvider):
    def __init__(self, config: AppConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self.client = client

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        async with self._client() as client:
            for account in self.config.ibkrAccounts:
                if not account.enabled:
                    continue
                assets.extend(await self._fetch_account_assets(client, account))
        return assets

    async def health_check(self) -> list[AccountStatus]:
        statuses: list[AccountStatus] = []
        async with self._client() as client:
            for account in self.config.ibkrAccounts:
                if not account.enabled:
                    statuses.append(
                        AccountStatus("ibkr", account.id, account.label, False, True, "disabled")
                    )
                    continue
                if not account.token or not account.queryId:
                    statuses.append(
                        AccountStatus(
                            "ibkr",
                            account.id,
                            account.label,
                            True,
                            False,
                            "missing credentials",
                        )
                    )
                    continue
                try:
                    reference_code = await self._send_request(client, account)
                    statuses.append(
                        AccountStatus(
                            "ibkr",
                            account.id,
                            account.label,
                            True,
                            True,
                            f"ok (reference {reference_code})",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    statuses.append(
                        AccountStatus(
                            "ibkr",
                            account.id,
                            account.label,
                            True,
                            False,
                            exc.__class__.__name__,
                        )
                    )
        return statuses

    async def _fetch_account_assets(
        self,
        client: httpx.AsyncClient,
        account: IbkrAccountConfig,
    ) -> list[Asset]:
        reference_code = await self._send_request(client, account)
        statement_xml = await self._get_statement(client, account, reference_code)
        return self._assets_from_statement_xml(account, statement_xml)

    async def _send_request(
        self,
        client: httpx.AsyncClient,
        account: IbkrAccountConfig,
    ) -> str:
        root = await self._get_xml(
            client,
            account,
            "/SendRequest",
            {"t": account.token, "q": account.queryId, "v": account.version},
        )
        self._raise_for_flex_error(root)
        reference_code = root.findtext("ReferenceCode")
        if not reference_code:
            raise RuntimeError("missing IBKR Flex reference code")
        return reference_code.strip()

    async def _get_statement(
        self,
        client: httpx.AsyncClient,
        account: IbkrAccountConfig,
        reference_code: str,
    ) -> ET.Element:
        last_error: Exception | None = None
        for attempt in range(account.statementRetries + 1):
            root = await self._get_xml(
                client,
                account,
                "/GetStatement",
                {"t": account.token, "q": reference_code, "v": account.version},
            )
            try:
                self._raise_for_flex_error(root)
                return root
            except RuntimeError as exc:
                last_error = exc
                if not self._is_transient_flex_error(root) or attempt >= account.statementRetries:
                    raise
                await asyncio.sleep(account.statementRetryDelaySeconds)
        raise last_error or RuntimeError("failed to retrieve IBKR Flex statement")

    def _assets_from_statement_xml(
        self,
        account: IbkrAccountConfig,
        root: ET.Element,
    ) -> list[Asset]:
        now = utc_now_iso()
        assets: list[Asset] = []
        for flex_statement in self._flex_statements(root):
            ibkr_account_id = (
                flex_statement.attrib.get("accountId") or account.accountId or account.id
            )
            if account.accountId is not None and ibkr_account_id != account.accountId:
                continue
            assets.extend(self._cash_assets(account, flex_statement, ibkr_account_id, now))
            assets.extend(self._position_assets(account, flex_statement, ibkr_account_id, now))
        return assets

    def _cash_assets(
        self,
        account: IbkrAccountConfig,
        flex_statement: ET.Element,
        ibkr_account_id: str,
        updated_at: str,
    ) -> list[Asset]:
        assets: list[Asset] = []
        for row in self._elements(flex_statement, "CashReportCurrency"):
            attrs = self._attrs(row)
            currency = self._str_attr(attrs, "currency").upper()
            if not currency or currency == "BASE":
                continue
            quantity = self._float_attr(attrs, "endingcash")
            if quantity == 0:
                continue
            rate = self._usd_rate(currency)
            value_usd = round(quantity * rate, 8)
            if value_usd == 0:
                continue
            assets.append(
                Asset(
                    source="ibkr",
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
                    rawSource="flex_cash_report",
                    wallet=ibkr_account_id,
                )
            )
        return assets

    def _position_assets(
        self,
        account: IbkrAccountConfig,
        flex_statement: ET.Element,
        ibkr_account_id: str,
        updated_at: str,
    ) -> list[Asset]:
        assets: list[Asset] = []
        for row in self._elements(flex_statement, "OpenPosition"):
            attrs = self._attrs(row)
            quantity = self._float_attr(attrs, "position")
            market_value = self._float_attr(attrs, "positionvalue")
            market_price = self._float_attr(attrs, "markprice")
            if quantity == 0 and market_value == 0:
                continue

            currency = (self._str_attr(attrs, "currency") or "USD").upper()
            rate = self._usd_rate(currency)
            value_usd = round((market_value or quantity * market_price) * rate, 8)
            if value_usd == 0:
                continue

            symbol = self._position_symbol(attrs)
            unit_price_usd = market_price * rate
            if unit_price_usd == 0 and quantity != 0:
                unit_price_usd = value_usd / quantity

            assets.append(
                Asset(
                    source="ibkr",
                    accountId=account.id,
                    accountLabel=account.label,
                    category="stock",
                    symbol=symbol,
                    name=self._str_attr(attrs, "description", "name") or symbol,
                    quantity=quantity,
                    currency=currency,
                    unitPriceUsd=round(unit_price_usd, 8),
                    valueUsd=value_usd,
                    updatedAt=updated_at,
                    rawSource="flex_open_positions",
                    wallet=ibkr_account_id,
                )
            )
        return assets

    async def _get_xml(
        self,
        client: httpx.AsyncClient,
        account: IbkrAccountConfig,
        path: str,
        params: dict[str, Any],
    ) -> ET.Element:
        response = await client.get(
            f"{account.baseUrl}{path}",
            params=params,
            headers={"User-Agent": f"asset-mcp/{__version__}"},
        )
        response.raise_for_status()
        return self._parse_xml(response.content)

    def _parse_xml(self, content: bytes) -> ET.Element:
        try:
            return ET.fromstring(content)
        except ET.ParseError as exc:
            raise RuntimeError("invalid IBKR Flex XML response") from exc

    def _raise_for_flex_error(self, root: ET.Element) -> None:
        status_text = root.findtext("Status")
        if status_text is None:
            return
        if status_text.strip() == "Success":
            return
        code = (root.findtext("ErrorCode") or "unknown").strip()
        raise RuntimeError(f"IBKR Flex request failed: {code}")

    def _is_transient_flex_error(self, root: ET.Element) -> bool:
        return (root.findtext("ErrorCode") or "") in TRANSIENT_FLEX_ERROR_CODES

    def _flex_statements(self, root: ET.Element) -> list[ET.Element]:
        if self._tag_name(root) == "FlexStatement":
            return [root]
        return self._elements(root, "FlexStatement")

    def _elements(self, root: ET.Element, tag_name: str) -> list[ET.Element]:
        return [element for element in root.iter() if self._tag_name(element) == tag_name]

    def _tag_name(self, element: ET.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    def _attrs(self, element: ET.Element) -> dict[str, str]:
        return {key.lower(): value for key, value in element.attrib.items()}

    def _position_symbol(self, attrs: dict[str, str]) -> str:
        return self._str_attr(attrs, "symbol").upper() or "UNKNOWN"

    def _str_attr(self, attrs: dict[str, str], *names: str) -> str:
        for name in names:
            value = attrs.get(name)
            if value:
                return value
        return ""

    def _float_attr(self, attrs: dict[str, str], *names: str) -> float:
        for name in names:
            value = attrs.get(name)
            if value is None or value == "":
                continue
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return 0.0
        return 0.0

    def _usd_rate(self, currency: str) -> float:
        return self.config.rates.get(currency, 1.0 if currency == "USD" else 0.0)

    def _client(self):
        if self.client is not None:
            return _NullAsyncContext(self.client)
        return httpx.AsyncClient(timeout=30, follow_redirects=True)


class _NullAsyncContext:
    def __init__(self, value: Any):
        self.value = value

    async def __aenter__(self) -> Any:
        return self.value

    async def __aexit__(self, *_args: Any) -> bool:
        return False
