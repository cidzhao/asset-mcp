from urllib.parse import urlparse

import httpx
import pytest

from asset_mcp.config import parse_config
from asset_mcp.providers.onchain import OnchainProvider


@pytest.mark.asyncio
async def test_onchain_provider_discovers_assets_from_addresses():
    config = parse_config(
        {
            "rates": {
                "BTC": 50000,
                "ETH": 2000,
                "SOL": 100,
                "TRX": 0.1,
                "USDT": 1,
                "USDD": 1,
                "SUSDD": 1.02,
            },
            "onchain": {
                "accounts": [
                    {
                        "id": "onchain-main",
                        "label": "On-chain Wallet",
                        "addresses": [
                            {"chain": "bitcoin", "address": "bc1qexample"},
                            {
                                "chain": "ethereum",
                                "address": "0x0000000000000000000000000000000000000001",
                            },
                            {
                                "chain": "501",
                                "address": "So11111111111111111111111111111111111111112",
                            },
                            {"chain": "tron", "address": "TXYZexample"},
                        ],
                    }
                ],
            },
        }
    )
    client = _FakeOnchainClient()

    assets = await OnchainProvider(config, client=client).fetch_assets()

    by_symbol_wallet = {(asset.symbol, asset.wallet): asset for asset in assets}
    assert by_symbol_wallet[("BTC", "bitcoin:bc1qexample")].quantity == 1
    assert by_symbol_wallet[("BTC", "bitcoin:bc1qexample")].valueUsd == 50000
    assert by_symbol_wallet[("ETH", "ethereum:0x0000...0001")].quantity == 2
    assert by_symbol_wallet[("ETH", "ethereum:0x0000...0001")].valueUsd == 4000
    assert by_symbol_wallet[("USDT", "ethereum:0x0000...0001")].quantity == 123.45
    assert by_symbol_wallet[("USDD", "ethereum:0x0000...0001")].quantity == 10
    assert by_symbol_wallet[("SUSDD", "ethereum:0x0000...0001")].valueUsd == 5.1
    assert by_symbol_wallet[("SOL", "solana:So1111...1112")].valueUsd == 300
    assert by_symbol_wallet[("JUP123...7890", "solana:So1111...1112")].valueUsd == 25
    assert by_symbol_wallet[("TRX", "tron:TXYZexample")].valueUsd == 0.5
    assert by_symbol_wallet[("USDT", "tron:TXYZexample")].valueUsd == 20


@pytest.mark.asyncio
async def test_onchain_provider_fetches_configured_erc20_tokens_with_indexer():
    config = parse_config(
        {
            "rates": {"CUSTOM": 2},
            "onchain": {
                "indexer": {"provider": "covalent", "apiKey": "test-key"},
                "accounts": [
                    {
                        "id": "onchain-main",
                        "label": "On-chain Wallet",
                        "addresses": [
                            {
                                "chain": "ethereum",
                                "address": "0x0000000000000000000000000000000000000001",
                                "tokens": [
                                    {
                                        "symbol": "USDT",
                                        "name": "Tether USD",
                                        "contractAddress": (
                                            "0xdAC17F958D2ee523a2206206994597C13D831ec7"
                                        ),
                                        "decimals": 6,
                                    },
                                    {
                                        "symbol": "CUSTOM",
                                        "name": "Custom Token",
                                        "contractAddress": (
                                            "0x00000000000000000000000000000000000000c0"
                                        ),
                                        "decimals": 18,
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
        }
    )

    assets = await OnchainProvider(config, client=_FakeOnchainClient()).fetch_assets()

    by_symbol = {asset.symbol: asset for asset in assets}
    assert by_symbol["ETH"].rawSource == "covalent_balances_v2"
    assert by_symbol["USDT"].rawSource == "covalent_balances_v2"
    assert by_symbol["CUSTOM"].quantity == 7
    assert by_symbol["CUSTOM"].valueUsd == 14
    assert by_symbol["CUSTOM"].rawSource == "configured_erc20_balance"
    assert [asset.symbol for asset in assets].count("USDT") == 1


@pytest.mark.asyncio
async def test_onchain_health_check_reports_unsupported_chain():
    config = parse_config(
        {
            "onchain": {
                "accounts": [
                    {
                        "id": "onchain-main",
                        "label": "On-chain Wallet",
                        "addresses": [{"chain": "unknown-chain", "address": "0x1"}],
                    }
                ]
            },
        }
    )

    statuses = await OnchainProvider(config, client=_FakeOnchainClient()).health_check()

    assert statuses[0].ok is False
    assert statuses[0].message == "ValueError"


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


class _FakeOnchainClient:
    async def get(self, url, **kwargs):
        parsed = urlparse(url)
        params = kwargs.get("params", {})
        if parsed.netloc == "blockstream.info" and parsed.path == "/api/address/bc1qexample":
            return _FakeResponse(
                200,
                {
                    "chain_stats": {"funded_txo_sum": 100000000, "spent_txo_sum": 0},
                    "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0},
                },
            )
        if parsed.netloc == "api.jup.ag" and parsed.path == "/price/v3":
            return _FakeResponse(200, {"JUP1234567890": {"usdPrice": 0.5}})
        if parsed.netloc == "api.covalenthq.com" and parsed.path.endswith("/balances_v2/"):
            return _FakeResponse(
                200,
                {
                    "data": {
                        "items": [
                            {
                                "contract_ticker_symbol": "ETH",
                                "contract_display_name": "Ethereum",
                                "contract_address": (
                                    "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
                                ),
                                "contract_decimals": 18,
                                "balance": str(2 * 10**18),
                                "quote_rate": 2000,
                                "quote": 4000,
                            },
                            {
                                "contract_ticker_symbol": "USDT",
                                "contract_display_name": "Tether USD",
                                "contract_address": (
                                    "0xdAC17F958D2ee523a2206206994597C13D831ec7"
                                ),
                                "contract_decimals": 6,
                                "balance": "123450000",
                                "quote_rate": 1,
                                "quote": 123.45,
                            },
                        ]
                    }
                },
            )
        if (
            parsed.netloc == "apilist.tronscanapi.com"
            and parsed.path == "/api/account/tokens"
            and params.get("address") == "TXYZexample"
        ):
            return _FakeResponse(
                200,
                {
                    "data": [
                        {"tokenAbbr": "TRX", "tokenName": "TRON", "quantity": 5, "priceInUsd": 0.1},
                        {
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "quantity": 20,
                            "priceInUsd": 1,
                        },
                    ]
                },
            )
        return _FakeResponse(404, {})

    async def post(self, url, **kwargs):
        parsed = urlparse(url)
        payload = kwargs.get("json", {})
        if parsed.netloc == "api.mainnet-beta.solana.com":
            if payload.get("method") == "getBalance":
                return _FakeResponse(200, {"result": {"value": 3 * 10**9}})
            if payload.get("method") == "getTokenAccountsByOwner":
                program_id = payload["params"][1]["programId"]
                if program_id.startswith("Tokenz"):
                    return _FakeResponse(200, {"result": {"value": []}})
                return _FakeResponse(
                    200,
                    {
                        "result": {
                            "value": [
                                {
                                    "account": {
                                        "data": {
                                            "parsed": {
                                                "info": {
                                                    "mint": "JUP1234567890",
                                                    "tokenAmount": {
                                                        "uiAmountString": "50",
                                                        "decimals": 6,
                                                    },
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    },
                )
        if parsed.netloc == "ethereum-rpc.publicnode.com":
            if payload.get("method") == "eth_getBalance":
                return _FakeResponse(200, {"result": hex(2 * 10**18)})
            if payload.get("method") == "eth_call":
                contract = payload["params"][0]["to"].lower()
                if contract == "0xdac17f958d2ee523a2206206994597c13d831ec7":
                    return _FakeResponse(200, {"result": hex(123450000)})
                if contract == "0x4f8e5de400de08b164e7421b3ee387f461becd1a":
                    return _FakeResponse(200, {"result": hex(10 * 10**18)})
                if contract == "0xc5d6a7b61d18afa11435a889557b068bb9f29930":
                    return _FakeResponse(200, {"result": hex(5 * 10**18)})
                if contract == "0x00000000000000000000000000000000000000c0":
                    return _FakeResponse(200, {"result": hex(7 * 10**18)})
                return _FakeResponse(200, {"result": "0x0"})
        return _FakeResponse(404, {})
