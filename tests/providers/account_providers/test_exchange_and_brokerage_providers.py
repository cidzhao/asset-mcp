import os
from urllib.parse import urlparse

import httpx
import pandas as pd
import pytest

from asset_mcp.config import parse_config
from asset_mcp.providers.brokerages.ibkr import IbkrProvider
from asset_mcp.providers.brokerages.longbridge import LongbridgeProvider
from asset_mcp.providers.brokerages.moomoo import MoomooProvider
from asset_mcp.providers.exchanges.binance import BinanceProvider
from asset_mcp.providers.exchanges.okx import OkxProvider


def test_binance_provider_converts_positive_spot_balances():
    config = parse_config(
        {
            "exchanges": {
                "binance": {
                    "accounts": [
                        {
                            "id": "binance-main",
                            "label": "Binance",
                            "apiKey": "key",
                            "apiSecret": "secret",
                        }
                    ]
                }
            }
        }
    )
    provider = BinanceProvider(config)

    assets = provider._assets_from_account(
        config.binanceAccounts[0],
        {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.1"},
                {"asset": "ETH", "free": "0", "locked": "0"},
                {"asset": "USDT", "free": "100", "locked": "0"},
            ]
        },
        {"BTC": 60000},
    )

    assert len(assets) == 2
    assert assets[0].accountId == "binance-main"
    assert assets[0].valueUsd == 36000
    assert assets[0].wallet == "spot"
    assert assets[1].symbol == "USDT"
    assert assets[1].valueUsd == 100


@pytest.mark.asyncio
async def test_binance_provider_converts_portfolio_margin_balances():
    config = _binance_config()
    client = _FakeBinanceClient(
        {
            ("GET", "papi.binance.com", "/papi/v1/balance"): [
                {"asset": "USD1", "totalWalletBalance": "1000"}
            ]
        }
    )

    assets = await BinanceProvider(config, client=client)._portfolio_margin_assets(
        client,
        config.binanceAccounts[0],
        {},
    )

    assert len(assets) == 1
    assert assets[0].wallet == "portfolio_margin"
    assert assets[0].rawSource == "portfolio_margin_balance"
    assert assets[0].valueUsd == 1000


def test_okx_provider_keeps_trading_and_funding_balances_separate():
    config = parse_config(
        {
            "exchanges": {
                "okx": {
                    "accounts": [
                        {
                            "id": "okx-main",
                            "label": "OKX",
                            "apiKey": "key",
                            "apiSecret": "secret",
                            "passphrase": "pass",
                        }
                    ]
                }
            }
        }
    )
    provider = OkxProvider(config)

    assets = provider._assets_from_balances(
        config.okxAccounts[0],
        {"data": [{"details": [{"ccy": "BTC", "cashBal": "0.1"}, {"ccy": "USDT", "eq": "50"}]}]},
        {"data": [{"ccy": "BTC", "bal": "0.2"}, {"ccy": "ETH", "bal": "1"}]},
        {"BTC": 60000, "ETH": 3000},
    )

    by_symbol_wallet = {(asset.symbol, asset.wallet): asset for asset in assets}
    assert by_symbol_wallet[("BTC", "trading")].quantity == 0.1
    assert by_symbol_wallet[("BTC", "trading")].valueUsd == 6000
    assert by_symbol_wallet[("BTC", "trading")].rawSource == "account_balance"
    assert by_symbol_wallet[("BTC", "funding")].quantity == 0.2
    assert by_symbol_wallet[("BTC", "funding")].valueUsd == 12000
    assert by_symbol_wallet[("BTC", "funding")].rawSource == "funding_balance"
    assert by_symbol_wallet[("USDT", "trading")].valueUsd == 50
    assert by_symbol_wallet[("ETH", "funding")].valueUsd == 3000


def test_moomoo_provider_uses_cash_by_real_currency_before_summary_currency():
    config = parse_config(
        {
            "rates": {"USD": 1, "HKD": 0.128},
            "brokers": {
                "moomoo": {
                    "accounts": [
                        {
                            "id": "moomoo-sg",
                            "label": "moomoo Singapore",
                            "trdMarket": "SG",
                            "securityFirm": "FUTUSG",
                        }
                    ]
                }
            },
        }
    )
    provider = MoomooProvider(config)

    assets = provider._assets_from_frames(
        config.moomooAccounts[0],
        pd.DataFrame(
            [
                {
                    "currency": "HKD",
                    "cash": 36488.49,
                    "us_cash": 4657.63,
                    "hk_cash": 0.0,
                }
            ]
        ),
        pd.DataFrame([]),
    )

    assert len(assets) == 1
    assert assets[0].symbol == "USD"
    assert assets[0].quantity == 4657.63
    assert assets[0].valueUsd == 4657.63
    assert assets[0].rawSource == "opend_accinfo_cash_by_currency"


def test_longbridge_provider_converts_cash_and_stock_positions():
    config = parse_config(
        {
            "rates": {"USD": 1, "HKD": 0.128},
            "brokers": {
                "longbridge": {
                    "accounts": [
                        {
                            "id": "longbridge-main",
                            "label": "Longbridge",
                            "appKey": "key",
                            "appSecret": "secret",
                            "accessToken": "token",
                        }
                    ]
                }
            },
        }
    )
    provider = LongbridgeProvider(config)

    assets = provider._assets_from_account_data(
        config.longbridgeAccounts[0],
        {
            "data": {
                "list": [
                    {
                        "currency": "HKD",
                        "total_cash": "1000",
                        "cash_infos": [
                            {
                                "currency": "USD",
                                "available_cash": "100",
                                "frozen_cash": "10",
                                "settling_cash": "-5",
                            },
                            {
                                "currency": "HKD",
                                "available_cash": "780",
                                "frozen_cash": "20",
                                "settling_cash": "0",
                            },
                        ],
                    }
                ]
            }
        },
        {
            "data": {
                "channels": [
                    {
                        "account_channel": "lb",
                        "positions": [
                            {
                                "symbol": "700.HK",
                                "symbol_name": "TENCENT",
                                "currency": "HKD",
                                "quantity": "2",
                                "cost_price": "300",
                            },
                            {
                                "symbol": "AAPL.US",
                                "symbol_name": "Apple",
                                "currency": "USD",
                                "quantity": "3",
                                "cost_price": "150",
                            },
                        ],
                    }
                ]
            }
        },
        {"700.HK": 400},
    )

    by_symbol = {asset.symbol: asset for asset in assets}
    assert by_symbol["USD"].quantity == 105
    assert by_symbol["USD"].valueUsd == 105
    assert by_symbol["HKD"].valueUsd == 102.4
    assert by_symbol["700.HK"].valueUsd == 102.4
    assert by_symbol["700.HK"].rawSource == "stock_positions_quote"
    assert by_symbol["AAPL.US"].valueUsd == 450
    assert by_symbol["AAPL.US"].rawSource == "stock_positions_cost_price"


def test_ibkr_provider_converts_flex_cash_and_open_positions():
    config = parse_config(
        {
            "rates": {"USD": 1, "HKD": 0.128},
            "brokers": {
                "ibkr": {
                    "accounts": [
                        {
                            "id": "ibkr-main",
                            "label": "IBKR Main",
                            "token": "token",
                            "queryId": "12345",
                            "accountId": "U1234567",
                        }
                    ]
                }
            },
        }
    )
    provider = IbkrProvider(config)

    root = provider._parse_xml(
        b"""
        <FlexQueryResponse>
          <FlexStatements count="1">
            <FlexStatement accountId="U1234567">
              <CashReport>
                <CashReportCurrency currency="USD" endingCash="1000" />
                <CashReportCurrency currency="HKD" endingCash="780" />
                <CashReportCurrency currency="BASE" endingCash="1099.84" />
              </CashReport>
              <OpenPositions>
                <OpenPosition symbol="AAPL" description="Apple Inc" position="3"
                  markPrice="200" positionValue="600" currency="USD" />
                <OpenPosition symbol="700" description="TENCENT" position="2"
                  markPrice="400" positionValue="800" currency="HKD" />
              </OpenPositions>
            </FlexStatement>
          </FlexStatements>
        </FlexQueryResponse>
        """
    )

    assets = provider._assets_from_statement_xml(
        config.ibkrAccounts[0],
        root,
    )

    by_symbol = {asset.symbol: asset for asset in assets}
    assert by_symbol["USD"].category == "cash"
    assert by_symbol["USD"].valueUsd == 1000
    assert by_symbol["HKD"].valueUsd == 99.84
    assert "BASE" not in by_symbol
    assert by_symbol["AAPL"].category == "stock"
    assert by_symbol["AAPL"].wallet == "U1234567"
    assert by_symbol["AAPL"].rawSource == "flex_open_positions"
    assert by_symbol["700"].valueUsd == 102.4


@pytest.mark.asyncio
async def test_ibkr_provider_fetches_flex_statement():
    config = parse_config(
        {
            "brokers": {
                "ibkr": {
                    "accounts": [
                        {
                            "id": "ibkr-main",
                            "label": "IBKR Main",
                            "token": "token",
                            "queryId": "12345",
                            "baseUrl": "https://example.test/flex",
                            "statementRetryDelaySeconds": 0,
                        }
                    ]
                }
            }
        }
    )
    client = _FakeFlexClient()

    assets = await IbkrProvider(config, client=client).fetch_assets()

    assert {asset.symbol for asset in assets} == {"USD", "AAPL"}
    assert client.calls == [
        (
            "/flex/SendRequest",
            {"t": "token", "q": "12345", "v": 3},
        ),
        (
            "/flex/GetStatement",
            {"t": "token", "q": "999999", "v": 3},
        ),
    ]


@pytest.mark.asyncio
async def test_longbridge_provider_redirects_sdk_stdout(capfd):
    config = parse_config(
        {
            "brokers": {
                "longbridge": {
                    "accounts": [
                        {
                            "id": "longbridge-main",
                            "label": "Longbridge",
                            "appKey": "key",
                            "appSecret": "secret",
                            "accessToken": "token",
                        }
                    ]
                }
            }
        }
    )
    provider = LongbridgeProvider(config)
    provider._import_sdk = lambda: _NoisyLongbridgeSdk

    assets = await provider.fetch_assets()

    captured = capfd.readouterr()
    assert captured.out == ""
    assert "quote permissions table" in captured.err
    assert len(assets) == 1
    assert assets[0].symbol == "AAPL.US"
    assert assets[0].unitPriceUsd == 200
    assert assets[0].valueUsd == 600


@pytest.mark.asyncio
async def test_binance_fetch_includes_portfolio_margin_and_skips_legacy_margin_routes():
    config = _binance_config()
    client = _FakeBinanceClient(
        {
            ("GET", "api.binance.com", "/api/v3/account"): {
                "balances": [{"asset": "BNB", "free": "1", "locked": "0"}]
            },
            ("GET", "api.binance.com", "/api/v3/ticker/price"): [
                {"symbol": "BNBUSDT", "price": "300"}
            ],
            ("GET", "api.binance.com", "/sapi/v1/asset/wallet/balance"): [],
            ("GET", "papi.binance.com", "/papi/v1/balance"): [
                {"asset": "USD1", "totalWalletBalance": "1000"}
            ],
            ("POST", "api.binance.com", "/sapi/v1/asset/get-funding-asset"): [],
            ("GET", "api.binance.com", "/sapi/v1/simple-earn/account"): {},
            ("GET", "api.binance.com", "/sapi/v1/simple-earn/flexible/position"): {
                "rows": [],
                "total": 0,
            },
            ("GET", "api.binance.com", "/sapi/v1/simple-earn/locked/position"): {
                "rows": [],
                "total": 0,
            },
            ("GET", "api.binance.com", "/sapi/v1/rwusd/account"): {},
            ("GET", "api.binance.com", "/sapi/v1/bfusd/account"): {},
        }
    )

    assets = await BinanceProvider(config, client=client).fetch_assets()

    by_wallet = {asset.wallet: asset for asset in assets}
    assert by_wallet["spot"].symbol == "BNB"
    assert by_wallet["spot"].valueUsd == 300
    assert by_wallet["portfolio_margin"].symbol == "USD1"
    assert by_wallet["portfolio_margin"].valueUsd == 1000
    assert not any(call[1] in {"fapi.binance.com", "dapi.binance.com"} for call in client.calls)
    assert not any(call[2] == "/sapi/v1/margin/account" for call in client.calls)


@pytest.mark.asyncio
async def test_binance_optional_endpoint_failures_still_return_spot_assets():
    config = _binance_config()
    client = _FakeBinanceClient(
        {
            ("GET", "api.binance.com", "/api/v3/account"): {
                "balances": [{"asset": "BNB", "free": "1", "locked": "0"}]
            },
            ("GET", "api.binance.com", "/api/v3/ticker/price"): [
                {"symbol": "BNBUSDT", "price": "300"}
            ],
        }
    )

    assets = await BinanceProvider(config, client=client).fetch_assets()

    assert len(assets) == 1
    assert assets[0].symbol == "BNB"
    assert assets[0].wallet == "spot"


def _binance_config():
    return parse_config(
        {
            "exchanges": {
                "binance": {
                    "accounts": [
                        {
                            "id": "binance-main",
                            "label": "Binance",
                            "apiKey": "key",
                            "apiSecret": "secret",
                        }
                    ]
                }
            }
        }
    )


class _FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.content = data if isinstance(data, bytes) else str(data).encode()

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code < 400:
            return
        request = httpx.Request("GET", "https://example.test")
        response = httpx.Response(self.status_code, json=self._data, request=request)
        raise httpx.HTTPStatusError("error", request=request, response=response)


class _FakeBinanceClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def get(self, url, **_kwargs):
        return self._response("GET", url)

    async def post(self, url, **_kwargs):
        return self._response("POST", url)

    def _response(self, method, url):
        parsed = urlparse(url)
        key = (method, parsed.netloc, parsed.path)
        self.calls.append(key)
        if key not in self.routes:
            return _FakeResponse(404, {"code": -1, "msg": "not configured"})
        return _FakeResponse(200, self.routes[key])


class _FakeFlexClient:
    def __init__(self):
        self.calls = []

    async def get(self, url, **kwargs):
        parsed = urlparse(url)
        params = kwargs.get("params", {})
        self.calls.append((parsed.path, params))
        if parsed.path.endswith("/SendRequest"):
            return _FakeResponse(
                200,
                b"""
                <FlexStatementResponse>
                  <Status>Success</Status>
                  <ReferenceCode>999999</ReferenceCode>
                </FlexStatementResponse>
                """,
            )
        if parsed.path.endswith("/GetStatement"):
            return _FakeResponse(
                200,
                b"""
                <FlexQueryResponse>
                  <FlexStatements count="1">
                    <FlexStatement accountId="U1234567">
                      <CashReport>
                        <CashReportCurrency currency="USD" endingCash="1000" />
                      </CashReport>
                      <OpenPositions>
                        <OpenPosition symbol="AAPL" description="Apple Inc"
                          position="3" markPrice="200" positionValue="600"
                          currency="USD" />
                      </OpenPositions>
                    </FlexStatement>
                  </FlexStatements>
                </FlexQueryResponse>
                """,
            )
        return _FakeResponse(404, b"<Error />")


class _NoisyLongbridgeSdk:
    class Config:
        @staticmethod
        def from_apikey(_app_key, _app_secret, _access_token):
            return object()

    class TradeContext:
        def __init__(self, _config):
            pass

        def account_balance(self):
            os.write(1, b"balance banner\n")
            return {"data": {"list": []}}

        def stock_positions(self):
            os.write(1, b"positions banner\n")
            return {
                "data": {
                    "channels": [
                        {
                            "account_channel": "lb_sg",
                            "positions": [
                                {
                                    "symbol": "AAPL.US",
                                    "symbol_name": "Apple",
                                    "currency": "USD",
                                    "quantity": "3",
                                    "cost_price": "150",
                                }
                            ],
                        }
                    ]
                }
            }

        def close(self):
            os.write(1, b"trade close banner\n")

    class QuoteContext:
        def __init__(self, _config):
            pass

        def quote(self, _symbols):
            os.write(1, b"quote permissions table\n")
            return [{"symbol": "AAPL.US", "last_done": "200"}]

        def close(self):
            os.write(1, b"quote close banner\n")
