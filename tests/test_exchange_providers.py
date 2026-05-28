from urllib.parse import urlparse

import httpx
import pandas as pd
import pytest

from asset_mcp.config import parse_config
from asset_mcp.providers.binance import BinanceProvider
from asset_mcp.providers.longbridge import LongbridgeProvider
from asset_mcp.providers.moomoo import MoomooProvider
from asset_mcp.providers.okx import OkxProvider


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
