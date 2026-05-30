from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BinanceAccountConfig:
    id: str
    label: str
    apiKey: str
    apiSecret: str
    enabled: bool = True
    environment: str = "production"


@dataclass(frozen=True)
class OkxAccountConfig:
    id: str
    label: str
    apiKey: str
    apiSecret: str
    passphrase: str
    enabled: bool = True
    environment: str = "production"
    domain: str = "https://www.okx.com"


@dataclass(frozen=True)
class MoomooAccountConfig:
    id: str
    label: str
    host: str = "127.0.0.1"
    port: int = 11111
    trdMarket: str = "US"
    securityFirm: str = "FUTUSECURITIES"
    accountId: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class LongbridgeAccountConfig:
    id: str
    label: str
    appKey: str = ""
    appSecret: str = ""
    accessToken: str = ""
    enabled: bool = True


@dataclass(frozen=True)
class IbkrAccountConfig:
    id: str
    label: str
    token: str = ""
    queryId: str = ""
    baseUrl: str = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
    accountId: str | None = None
    version: int = 3
    statementRetries: int = 3
    statementRetryDelaySeconds: float = 5.0
    enabled: bool = True


@dataclass(frozen=True)
class OnchainIndexerConfig:
    provider: str = "covalent"
    apiKey: str = ""
    baseUrl: str = "https://api.covalenthq.com/v1"


@dataclass(frozen=True)
class OnchainTokenConfig:
    symbol: str
    contractAddress: str
    decimals: int
    name: str | None = None
    coinGeckoId: str | None = None


@dataclass(frozen=True)
class OnchainAddressConfig:
    chain: str
    address: str
    label: str | None = None
    tokens: list[OnchainTokenConfig] = field(default_factory=list)
    rpcUrl: str | None = None
    explorerApiUrl: str | None = None


@dataclass(frozen=True)
class OnchainAccountConfig:
    id: str
    label: str
    addresses: list[OnchainAddressConfig]
    enabled: bool = True


@dataclass(frozen=True)
class ManualAssetConfig:
    symbol: str
    quantity: float
    currency: str
    name: str | None = None


@dataclass(frozen=True)
class ManualAccountConfig:
    id: str
    label: str
    category: str
    assets: list[ManualAssetConfig]
    enabled: bool = True


@dataclass(frozen=True)
class AppConfig:
    baseCurrency: str = "USD"
    rates: dict[str, float] = field(default_factory=lambda: {"USD": 1.0, "USDT": 1.0})
    binanceAccounts: list[BinanceAccountConfig] = field(default_factory=list)
    okxAccounts: list[OkxAccountConfig] = field(default_factory=list)
    moomooAccounts: list[MoomooAccountConfig] = field(default_factory=list)
    longbridgeAccounts: list[LongbridgeAccountConfig] = field(default_factory=list)
    ibkrAccounts: list[IbkrAccountConfig] = field(default_factory=list)
    onchainIndexer: OnchainIndexerConfig = field(default_factory=OnchainIndexerConfig)
    onchainAccounts: list[OnchainAccountConfig] = field(default_factory=list)
    manualAccounts: list[ManualAccountConfig] = field(default_factory=list)
