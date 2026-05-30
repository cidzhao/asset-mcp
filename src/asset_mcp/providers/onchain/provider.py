from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from asset_mcp.config import AppConfig, OnchainAccountConfig, OnchainAddressConfig
from asset_mcp.domain.models import AccountStatus, Asset, utc_now_iso
from asset_mcp.providers.base import AssetProvider


COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
JUPITER_PRICE_URL = "https://api.jup.ag/price/v3"
SOLANA_TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SOLANA_TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFsc9WtZb7u9fKjffNb"
STABLE_USD_SYMBOLS = {"USD", "USDT", "USDC", "DAI", "BUSD", "FDUSD"}


@dataclass(frozen=True)
class ChainSpec:
    key: str
    name: str
    symbol: str
    coin_gecko_id: str
    kind: str
    decimals: int
    chain_id: str | None = None
    rpc_url: str | None = None
    explorer_api_url: str | None = None


@dataclass(frozen=True)
class EvmTokenSpec:
    symbol: str
    name: str
    contract_address: str
    decimals: int
    coin_gecko_id: str


CHAIN_ALIASES = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "0": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "1": "ethereum",
    "sol": "solana",
    "solana": "solana",
    "501": "solana",
    "bnb": "bsc",
    "bsc": "bsc",
    "56": "bsc",
    "tron": "tron",
    "trx": "tron",
    "polygon": "polygon",
    "matic": "polygon",
    "137": "polygon",
    "avalanche": "avalanche",
    "avax": "avalanche",
    "43114": "avalanche",
    "arbitrum": "arbitrum",
    "arbitrum-one": "arbitrum",
    "42161": "arbitrum",
    "base": "base",
    "8453": "base",
    "optimism": "optimism",
    "op": "optimism",
    "10": "optimism",
}


SUPPORTED_CHAINS = {
    "bitcoin": ChainSpec(
        "bitcoin",
        "Bitcoin",
        "BTC",
        "bitcoin",
        "bitcoin",
        8,
        explorer_api_url="https://blockstream.info/api",
    ),
    "ethereum": ChainSpec(
        "ethereum",
        "Ethereum",
        "ETH",
        "ethereum",
        "evm",
        18,
        chain_id="1",
        rpc_url="https://ethereum-rpc.publicnode.com",
    ),
    "solana": ChainSpec(
        "solana",
        "Solana",
        "SOL",
        "solana",
        "solana",
        9,
        rpc_url="https://api.mainnet-beta.solana.com",
    ),
    "bsc": ChainSpec(
        "bsc",
        "BNB Smart Chain",
        "BNB",
        "binancecoin",
        "evm",
        18,
        chain_id="56",
        rpc_url="https://bsc-rpc.publicnode.com",
    ),
    "tron": ChainSpec(
        "tron",
        "TRON",
        "TRX",
        "tron",
        "tron",
        6,
        explorer_api_url="https://apilist.tronscanapi.com/api",
    ),
    "polygon": ChainSpec(
        "polygon",
        "Polygon",
        "MATIC",
        "matic-network",
        "evm",
        18,
        chain_id="137",
        rpc_url="https://polygon-bor-rpc.publicnode.com",
    ),
    "avalanche": ChainSpec(
        "avalanche",
        "Avalanche C-Chain",
        "AVAX",
        "avalanche-2",
        "evm",
        18,
        chain_id="43114",
        rpc_url="https://avalanche-c-chain-rpc.publicnode.com",
    ),
    "arbitrum": ChainSpec(
        "arbitrum",
        "Arbitrum One",
        "ETH",
        "ethereum",
        "evm",
        18,
        chain_id="42161",
        rpc_url="https://arbitrum-one-rpc.publicnode.com",
    ),
    "base": ChainSpec(
        "base",
        "Base",
        "ETH",
        "ethereum",
        "evm",
        18,
        chain_id="8453",
        rpc_url="https://base-rpc.publicnode.com",
    ),
    "optimism": ChainSpec(
        "optimism",
        "Optimism",
        "ETH",
        "ethereum",
        "evm",
        18,
        chain_id="10",
        rpc_url="https://optimism-rpc.publicnode.com",
    ),
}


COMMON_EVM_TOKENS = {
    "ethereum": [
        EvmTokenSpec("USDT", "Tether USD", "0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, "tether"),
        EvmTokenSpec("USDC", "USD Coin", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, "usd-coin"),
        EvmTokenSpec("DAI", "Dai", "0x6B175474E89094C44Da98b954EedeAC495271d0F", 18, "dai"),
        EvmTokenSpec("USDD", "USDD Stablecoin", "0x4f8e5de400de08b164e7421b3ee387f461becd1a", 18, "usdd"),
        EvmTokenSpec("SUSDD", "Savings USDD", "0xC5d6A7B61d18AfA11435a889557b068BB9f29930", 18, "savings-usdd"),
        EvmTokenSpec("WBTC", "Wrapped Bitcoin", "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8, "wrapped-bitcoin"),
        EvmTokenSpec("WETH", "Wrapped Ether", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18, "weth"),
        EvmTokenSpec("LINK", "Chainlink", "0x514910771AF9Ca656af840dff83E8264EcF986CA", 18, "chainlink"),
        EvmTokenSpec("UNI", "Uniswap", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984", 18, "uniswap"),
    ],
    "bsc": [
        EvmTokenSpec("USDT", "Tether USD", "0x55d398326f99059fF775485246999027B3197955", 18, "tether"),
        EvmTokenSpec("USDC", "USD Coin", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18, "usd-coin"),
        EvmTokenSpec("BTCB", "BTCB Token", "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c", 18, "binance-bitcoin"),
        EvmTokenSpec("ETH", "Binance-Peg Ethereum", "0x2170Ed0880ac9A755fd29B2688956BD959F933F8", 18, "ethereum"),
        EvmTokenSpec("BUSD", "BUSD Token", "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56", 18, "binance-usd"),
    ],
    "polygon": [
        EvmTokenSpec("USDT", "Tether USD", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", 6, "tether"),
        EvmTokenSpec("USDC.E", "USD Coin", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6, "usd-coin"),
        EvmTokenSpec("DAI", "Dai", "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", 18, "dai"),
        EvmTokenSpec("WBTC", "Wrapped Bitcoin", "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6", 8, "wrapped-bitcoin"),
        EvmTokenSpec("WETH", "Wrapped Ether", "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", 18, "weth"),
    ],
    "avalanche": [
        EvmTokenSpec("USDC", "USD Coin", "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", 6, "usd-coin"),
        EvmTokenSpec("USDT", "Tether USD", "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7", 6, "tether"),
        EvmTokenSpec("WETH.E", "Wrapped Ether", "0x49D5c2BdFfac6CE2BFdB6640F4F80f226bc10bAB", 18, "weth"),
        EvmTokenSpec("WBTC.E", "Wrapped Bitcoin", "0x50b7545627a5162F82A992c33b87aDc75187B218", 8, "wrapped-bitcoin"),
        EvmTokenSpec("DAI.E", "Dai", "0xd586E7F844cEa2F87f50152665BCbc2C279D8d70", 18, "dai"),
    ],
    "arbitrum": [
        EvmTokenSpec("USDT", "Tether USD", "0xFd086bC7CD5C481DCC9C85ebe478A1C0b69FCbb9", 6, "tether"),
        EvmTokenSpec("USDC", "USD Coin", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6, "usd-coin"),
        EvmTokenSpec("USDC.E", "Bridged USDC", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", 6, "usd-coin"),
        EvmTokenSpec("WBTC", "Wrapped Bitcoin", "0x2f2a2543B76a4166549F7aaB2e75Bef0aefC5B0f", 8, "wrapped-bitcoin"),
        EvmTokenSpec("WETH", "Wrapped Ether", "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 18, "weth"),
    ],
    "base": [
        EvmTokenSpec("USDC", "USD Coin", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6, "usd-coin"),
        EvmTokenSpec("WETH", "Wrapped Ether", "0x4200000000000000000000000000000000000006", 18, "weth"),
        EvmTokenSpec("CBBTC", "Coinbase Wrapped BTC", "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf", 8, "coinbase-wrapped-btc"),
    ],
    "optimism": [
        EvmTokenSpec("USDT", "Tether USD", "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58", 6, "tether"),
        EvmTokenSpec("USDC", "USD Coin", "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", 6, "usd-coin"),
        EvmTokenSpec("USDC.E", "Bridged USDC", "0x7F5c764cBc14f9669B88837ca1490cCa17c31607", 6, "usd-coin"),
        EvmTokenSpec("WBTC", "Wrapped Bitcoin", "0x68f180fcCe6836688e9084f035309E29Bf0A2095", 8, "wrapped-bitcoin"),
        EvmTokenSpec("WETH", "Wrapped Ether", "0x4200000000000000000000000000000000000006", 18, "weth"),
    ],
}


class OnchainProvider(AssetProvider):
    def __init__(self, config: AppConfig, client: httpx.AsyncClient | None = None):
        self.config = config
        self.client = client

    async def fetch_assets(self) -> list[Asset]:
        assets: list[Asset] = []
        async with self._client() as client:
            for account in self.config.onchainAccounts:
                if not account.enabled:
                    continue
                assets.extend(await self._fetch_account_assets(client, account))
        return assets

    async def health_check(self) -> list[AccountStatus]:
        statuses: list[AccountStatus] = []
        async with self._client() as client:
            for account in self.config.onchainAccounts:
                if not account.enabled:
                    statuses.append(
                        AccountStatus("onchain", account.id, account.label, False, True, "disabled")
                    )
                    continue
                if not account.addresses:
                    statuses.append(
                        AccountStatus(
                            "onchain",
                            account.id,
                            account.label,
                            True,
                            False,
                            "missing addresses",
                        )
                    )
                    continue
                try:
                    assets = await self._fetch_account_assets(client, account)
                    statuses.append(
                        AccountStatus(
                            "onchain",
                            account.id,
                            account.label,
                            True,
                            True,
                            f"covered {len(account.addresses)} addresses, {len(assets)} assets",
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    statuses.append(
                        AccountStatus(
                            "onchain",
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
        account: OnchainAccountConfig,
    ) -> list[Asset]:
        prices: dict[str, float] | None = None
        assets: list[Asset] = []
        for address in account.addresses:
            spec = _chain_spec(address.chain)
            if spec.kind == "evm":
                if self.config.onchainIndexer.apiKey:
                    indexed_assets, indexed_contracts = await self._covalent_assets(
                        client,
                        account,
                        address,
                        spec,
                    )
                    assets.extend(indexed_assets)
                    assets.extend(
                        await self._configured_evm_assets(
                            client,
                            account,
                            address,
                            spec,
                            skip_contracts=indexed_contracts,
                        )
                    )
                else:
                    assets.extend(await self._evm_common_assets(client, account, address, spec))
            elif spec.kind == "bitcoin":
                prices = prices or await self._native_price_map(client, account)
                assets.extend(await self._bitcoin_assets(client, account, address, spec, prices))
            elif spec.kind == "solana":
                prices = prices or await self._native_price_map(client, account)
                assets.extend(await self._solana_assets(client, account, address, spec, prices))
            elif spec.kind == "tron":
                prices = prices or await self._native_price_map(client, account)
                assets.extend(await self._tron_assets(client, account, address, spec, prices))
            else:
                raise ValueError(f"Unsupported on-chain balance kind '{spec.kind}'.")
        return assets

    async def _evm_common_assets(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
        address: OnchainAddressConfig,
        spec: ChainSpec,
    ) -> list[Asset]:
        holdings: list[tuple[str, str, float, str, str]] = []
        native_quantity = await self._evm_native_quantity(client, spec, address)
        if native_quantity > 0:
            holdings.append(
                (
                    spec.symbol,
                    f"{spec.name} {spec.symbol}",
                    native_quantity,
                    spec.coin_gecko_id,
                    "onchain_native_balance",
                )
            )

        for token in _evm_tokens_for_address(spec, address):
            raw_balance = await self._evm_token_balance(client, spec, address, token.contract_address)
            quantity = raw_balance / (10**token.decimals)
            if quantity > 0:
                holdings.append(
                    (
                        token.symbol,
                        token.name,
                        quantity,
                        token.coin_gecko_id,
                        "common_evm_token_balance",
                    )
                )

        prices = await self._price_map_for_coin_ids(
            client,
            {coin_id: symbol for symbol, _name, _quantity, coin_id, _source in holdings},
        )
        assets = []
        for symbol, name, quantity, _coin_id, raw_source in holdings:
            asset = _asset(
                account,
                address,
                spec,
                symbol=symbol,
                quantity=quantity,
                unit_price_usd=prices.get(symbol.upper(), 0.0),
                name=name,
                raw_source=raw_source,
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _configured_evm_assets(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
        address: OnchainAddressConfig,
        spec: ChainSpec,
        skip_contracts: set[str] | None = None,
    ) -> list[Asset]:
        skip_contracts = skip_contracts or set()
        holdings: list[tuple[str, str, float, str]] = []
        for token in address.tokens:
            contract_address = token.contractAddress.lower()
            if contract_address in skip_contracts:
                continue
            raw_balance = await self._evm_token_balance(
                client,
                spec,
                address,
                token.contractAddress,
            )
            quantity = raw_balance / (10**token.decimals)
            if quantity > 0:
                holdings.append(
                    (
                        token.symbol.upper(),
                        token.name or token.symbol.upper(),
                        quantity,
                        token.coinGeckoId or "",
                    )
                )

        prices = await self._price_map_for_coin_ids(
            client,
            {
                coin_id: symbol
                for symbol, _name, _quantity, coin_id in holdings
                if coin_id
            },
        )
        assets = []
        for symbol, name, quantity, _coin_id in holdings:
            asset = _asset(
                account,
                address,
                spec,
                symbol=symbol,
                quantity=quantity,
                unit_price_usd=prices.get(symbol.upper(), 0.0),
                name=name,
                raw_source="configured_erc20_balance",
            )
            if asset is not None:
                assets.append(asset)
        return assets

    async def _covalent_assets(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
        address: OnchainAddressConfig,
        spec: ChainSpec,
    ) -> tuple[list[Asset], set[str]]:
        if self.config.onchainIndexer.provider.lower() != "covalent":
            raise ValueError("Only covalent on-chain indexer is supported.")
        if not self.config.onchainIndexer.apiKey:
            raise ValueError("Covalent API key is required for EVM asset discovery.")
        if not spec.chain_id:
            raise ValueError(f"Missing Covalent chain id for '{spec.key}'.")

        response = await client.get(
            f"{self.config.onchainIndexer.baseUrl}/{spec.chain_id}/address/"
            f"{address.address}/balances_v2/",
            params={
                "key": self.config.onchainIndexer.apiKey,
                "quote-currency": "USD",
                "nft": "true",
                "no-nft-fetch": "true",
            },
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        rows = data.get("items", []) if isinstance(data, dict) else []
        assets = []
        indexed_contracts: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or row.get("is_spam") is True:
                continue
            contract_address = str(row.get("contract_address") or "").lower()
            if contract_address:
                indexed_contracts.add(contract_address)
            asset = _asset_from_indexed_row(account, address, spec, row)
            if asset is not None:
                assets.append(asset)
        return assets, indexed_contracts

    async def _evm_native_quantity(
        self,
        client: httpx.AsyncClient,
        spec: ChainSpec,
        address: OnchainAddressConfig,
    ) -> float:
        data = await self._json_rpc(
            client,
            _rpc_url(spec, address),
            "eth_getBalance",
            [address.address, "latest"],
        )
        return _int_from_hex(data.get("result")) / (10**spec.decimals)

    async def _evm_token_balance(
        self,
        client: httpx.AsyncClient,
        spec: ChainSpec,
        address: OnchainAddressConfig,
        contract_address: str,
    ) -> int:
        if not address.address.lower().startswith("0x"):
            raise ValueError("EVM token balance requires a hex address.")
        padded_address = address.address.removeprefix("0x").removeprefix("0X").rjust(64, "0")
        data = await self._json_rpc(
            client,
            _rpc_url(spec, address),
            "eth_call",
            [{"to": contract_address, "data": f"0x70a08231{padded_address}"}, "latest"],
        )
        return _int_from_hex(data.get("result"))

    async def _bitcoin_assets(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
        address: OnchainAddressConfig,
        spec: ChainSpec,
        prices: dict[str, float],
    ) -> list[Asset]:
        response = await client.get(f"{_explorer_api_url(spec, address)}/address/{address.address}")
        response.raise_for_status()
        data = response.json()
        chain_stats = data.get("chain_stats") or {}
        mempool_stats = data.get("mempool_stats") or {}
        funded = int(chain_stats.get("funded_txo_sum", 0)) + int(
            mempool_stats.get("funded_txo_sum", 0)
        )
        spent = int(chain_stats.get("spent_txo_sum", 0)) + int(
            mempool_stats.get("spent_txo_sum", 0)
        )
        quantity = (funded - spent) / (10 ** spec.decimals)
        asset = _asset_from_quantity(account, address, spec, spec.symbol, quantity, prices)
        return [asset] if asset is not None else []

    async def _solana_assets(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
        address: OnchainAddressConfig,
        spec: ChainSpec,
        prices: dict[str, float],
    ) -> list[Asset]:
        assets = []
        balance = await self._json_rpc(
            client,
            _rpc_url(spec, address),
            "getBalance",
            [address.address],
        )
        native_quantity = int((balance.get("result") or {}).get("value", 0)) / (10**spec.decimals)
        native = _asset_from_quantity(account, address, spec, spec.symbol, native_quantity, prices)
        if native is not None:
            assets.append(native)

        token_rows = []
        for program_id in (SOLANA_TOKEN_PROGRAM_ID, SOLANA_TOKEN_2022_PROGRAM_ID):
            data = await self._json_rpc(
                client,
                _rpc_url(spec, address),
                "getTokenAccountsByOwner",
                [
                    address.address,
                    {"programId": program_id},
                    {"encoding": "jsonParsed"},
                ],
            )
            token_rows.extend((data.get("result") or {}).get("value", []))

        token_holdings = _solana_token_holdings(token_rows)
        token_prices = await self._jupiter_prices(client, list(token_holdings))
        for mint, quantity in token_holdings.items():
            if quantity <= 0:
                continue
            unit_price = token_prices.get(mint, 0.0)
            assets.append(
                _asset(
                    account,
                    address,
                    spec,
                    symbol=_short_address(mint),
                    quantity=quantity,
                    unit_price_usd=unit_price,
                    name=f"Solana token {mint}",
                    raw_source="solana_token_accounts",
                )
            )
        return assets

    async def _tron_assets(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
        address: OnchainAddressConfig,
        spec: ChainSpec,
        prices: dict[str, float],
    ) -> list[Asset]:
        response = await client.get(
            f"{_explorer_api_url(spec, address)}/account/tokens",
            params={
                "address": address.address,
                "start": 0,
                "limit": 200,
                "hidden": 0,
                "show": 0,
            },
        )
        response.raise_for_status()
        data = response.json()
        rows = data.get("data", []) if isinstance(data, dict) else []
        assets = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("tokenAbbr") or row.get("tokenName") or "").upper()
            if not symbol:
                continue
            quantity = _float(row.get("quantity") or row.get("amount"))
            if quantity <= 0:
                continue
            unit_price = _float(row.get("priceInUsd") or row.get("price"))
            if unit_price <= 0:
                unit_price = prices.get(symbol, 0.0)
            assets.append(
                _asset(
                    account,
                    address,
                    spec,
                    symbol=symbol,
                    quantity=quantity,
                    unit_price_usd=unit_price,
                    name=str(row.get("tokenName") or symbol),
                    raw_source="tronscan_account_tokens",
                )
            )
        return assets

    async def _native_price_map(
        self,
        client: httpx.AsyncClient,
        account: OnchainAccountConfig,
    ) -> dict[str, float]:
        coin_ids: dict[str, str] = {}
        for address in account.addresses:
            spec = _chain_spec(address.chain)
            if spec.kind == "evm":
                continue
            coin_ids[spec.coin_gecko_id] = spec.symbol.upper()
        return await self._price_map_for_coin_ids(client, coin_ids)

    async def _price_map_for_coin_ids(
        self,
        client: httpx.AsyncClient,
        coin_ids: dict[str, str],
    ) -> dict[str, float]:
        prices = {symbol.upper(): price for symbol, price in self.config.rates.items()}
        for symbol in STABLE_USD_SYMBOLS:
            prices.setdefault(symbol, 1.0)
        missing_ids = [
            coin_id
            for coin_id, symbol in coin_ids.items()
            if coin_id and prices.get(symbol, 0.0) <= 0
        ]
        if not missing_ids:
            return prices

        response = await client.get(
            COINGECKO_PRICE_URL,
            params={"ids": ",".join(sorted(missing_ids)), "vs_currencies": "usd"},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return prices
        for coin_id in missing_ids:
            price = _float((data.get(coin_id) or {}).get("usd"))
            if price > 0:
                prices[coin_ids[coin_id]] = price
        return prices

    async def _jupiter_prices(
        self,
        client: httpx.AsyncClient,
        mints: list[str],
    ) -> dict[str, float]:
        if not mints:
            return {}
        try:
            response = await client.get(JUPITER_PRICE_URL, params={"ids": ",".join(mints[:50])})
            response.raise_for_status()
        except Exception:  # noqa: BLE001
            return {}
        data = response.json()
        if not isinstance(data, dict):
            return {}
        return {mint: _float((data.get(mint) or {}).get("usdPrice")) for mint in mints}

    async def _json_rpc(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str,
        params: list[Any],
    ) -> dict[str, Any]:
        response = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON-RPC response.")
        if data.get("error"):
            raise ValueError("JSON-RPC error.")
        return data

    def _client(self):
        if self.client is not None:
            return _NullAsyncContext(self.client)
        return httpx.AsyncClient(timeout=20)


def _asset_from_indexed_row(
    account: OnchainAccountConfig,
    address: OnchainAddressConfig,
    spec: ChainSpec,
    row: dict[str, Any],
) -> Asset | None:
    decimals = int(row.get("contract_decimals") or 0)
    quantity = _float(row.get("balance")) / (10**decimals)
    if quantity <= 0:
        return None
    symbol = str(row.get("contract_ticker_symbol") or "").upper()
    if not symbol:
        symbol = _short_address(str(row.get("contract_address") or spec.symbol))
    unit_price = _float(row.get("quote_rate"))
    value_usd = _float(row.get("quote"))
    if unit_price <= 0 and value_usd > 0:
        unit_price = value_usd / quantity
    if value_usd <= 0 and unit_price > 0:
        value_usd = quantity * unit_price
    return _asset(
        account,
        address,
        spec,
        symbol=symbol,
        quantity=quantity,
        unit_price_usd=unit_price,
        value_usd=value_usd,
        name=str(row.get("contract_display_name") or row.get("contract_name") or symbol),
        raw_source="covalent_balances_v2",
    )


def _asset_from_quantity(
    account: OnchainAccountConfig,
    address: OnchainAddressConfig,
    spec: ChainSpec,
    symbol: str,
    quantity: float,
    prices: dict[str, float],
    name: str | None = None,
    raw_source: str = "onchain_native_balance",
) -> Asset | None:
    unit_price_usd = prices.get(symbol.upper(), 0.0)
    return _asset(
        account,
        address,
        spec,
        symbol=symbol,
        quantity=quantity,
        unit_price_usd=unit_price_usd,
        name=name or f"{spec.name} {symbol}",
        raw_source=raw_source,
    )


def _asset(
    account: OnchainAccountConfig,
    address: OnchainAddressConfig,
    spec: ChainSpec,
    symbol: str,
    quantity: float,
    unit_price_usd: float,
    name: str | None,
    raw_source: str,
    value_usd: float | None = None,
) -> Asset | None:
    if quantity <= 0:
        return None
    symbol = symbol.upper()
    if value_usd is None:
        value_usd = quantity * unit_price_usd
    wallet = address.label or f"{spec.key}:{_short_address(address.address)}"
    return Asset(
        source="onchain",
        accountId=account.id,
        accountLabel=account.label,
        category="crypto",
        symbol=symbol,
        quantity=quantity,
        currency=symbol,
        unitPriceUsd=round(unit_price_usd, 8),
        valueUsd=round(value_usd, 8),
        updatedAt=utc_now_iso(),
        name=name,
        rawSource=raw_source,
        wallet=wallet,
    )


def _solana_token_holdings(rows: list[dict[str, Any]]) -> dict[str, float]:
    holdings: dict[str, float] = {}
    for row in rows:
        info = (
            ((row.get("account") or {}).get("data") or {})
            .get("parsed", {})
            .get("info", {})
        )
        mint = str(info.get("mint") or "")
        token_amount = info.get("tokenAmount") or {}
        quantity = _float(token_amount.get("uiAmountString") or token_amount.get("uiAmount"))
        if mint and quantity > 0:
            holdings[mint] = holdings.get(mint, 0.0) + quantity
    return holdings


def _evm_tokens_for_address(
    spec: ChainSpec,
    address: OnchainAddressConfig,
) -> list[EvmTokenSpec]:
    tokens_by_contract = {
        token.contract_address.lower(): token for token in COMMON_EVM_TOKENS.get(spec.key, [])
    }
    for token in address.tokens:
        tokens_by_contract[token.contractAddress.lower()] = EvmTokenSpec(
            token.symbol.upper(),
            token.name or token.symbol.upper(),
            token.contractAddress,
            token.decimals,
            token.coinGeckoId or "",
        )
    return list(tokens_by_contract.values())


def _chain_spec(chain: str) -> ChainSpec:
    normalized = chain.strip().lower().replace(" ", "-")
    key = CHAIN_ALIASES.get(normalized)
    if key is None or key not in SUPPORTED_CHAINS:
        raise ValueError(f"Unsupported on-chain network '{chain}'.")
    return SUPPORTED_CHAINS[key]


def _rpc_url(spec: ChainSpec, address: OnchainAddressConfig) -> str:
    url = address.rpcUrl or spec.rpc_url
    if not url:
        raise ValueError(f"Missing RPC URL for '{spec.key}'.")
    return url.rstrip("/")


def _explorer_api_url(spec: ChainSpec, address: OnchainAddressConfig) -> str:
    url = address.explorerApiUrl or spec.explorer_api_url
    if not url:
        raise ValueError(f"Missing explorer API URL for '{spec.key}'.")
    return url.rstrip("/")


def _short_address(address: str) -> str:
    if len(address) <= 12:
        return address
    return f"{address[:6]}...{address[-4:]}"


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int_from_hex(value: Any) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        return 0
    return int(value, 16)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return exc.__class__.__name__


class _NullAsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False
