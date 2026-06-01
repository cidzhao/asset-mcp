# Asset MCP

[English](README.md)

Asset MCP 是一个只读的 Python MCP 服务器，用于聚合 Binance、OKX、
moomoo OpenD、Longbridge、IBKR、链上钱包以及手动配置账户中的个人资产。

它向任何兼容 MCP 的 AI 客户端暴露标准化资产数据。它不会交易、转账、提现，
也不会自动化银行或支付宝访问。

## 功能

- 支持多个 Binance 账户。
- 支持多个 OKX 账户。
- 支持多个 moomoo/Futu OpenD 账户。
- 支持多个 Longbridge OpenAPI 账户。
- 支持多个 IBKR Flex Web Service 账户。
- 支持 BTC、ETH、SOL、BSC、TRON、Polygon、Avalanche、Arbitrum、Base 和
  Optimism 的链上钱包地址。
- 支持银行、支付宝、现金、房产以及其他线下账户的手动资产。
- 以美元计价的净资产汇总。
- 面向 AI 生成图表的仪表盘分组数据。

## 环境要求

- Python `>=3.10`。
- 如果启用交易所账户，需要只读 Binance/OKX API key。
- 如果启用 moomoo 账户，需要安装、启动并登录 moomoo/Futu OpenD。
- 如果启用 Longbridge 账户，需要 Longbridge OpenAPI API key 凭据。
- 如果启用 IBKR 账户，需要 IBKR Flex Web Service token 和 Flex Query ID。
- 如果启用链上钱包账户，需要公开钱包地址。
- `uv` 只用于本地开发；普通用户可以直接用 `pip` 安装。

## 快速开始

```bash
# 1. 从 PyPI 安装
pip install asset-mcp

# 2. 创建初始配置文件 (~/.config/asset-mcp/config.local.yaml)
asset-mcp init

# 3. 编辑配置：填写至少一个账户的凭据，并设置 `enabled: true`。
#    每个 provider 的配置示例见下方 “配置”。
vim ~/.config/asset-mcp/config.local.yaml

# 4. 在 MCP 客户端中注册服务器
claude mcp add asset-mcp -- asset-mcp
# 或
codex mcp add asset-mcp -- asset-mcp

# 5. 验证：让客户端调用 `health_check_sources` 工具。
#    每个启用的账户都应该返回 `ok: true`。
```

![Install and register](https://raw.githubusercontent.com/cidzhao/asset-mcp/main/media/quick-start.gif)

最小可用配置不需要任何 API key。只配置一个手动现金账户，就足够确认安装可用：

```yaml
baseCurrency: USD
rates:
  USD: 1.0
  CNY: 0.14
manual:
  accounts:
    - id: cash
      label: Cash on hand
      enabled: true
      category: cash
      assets:
        - symbol: CNY
          quantity: 10000
          currency: CNY
```

## 安装

从 PyPI 安装：

```bash
pip install asset-mcp
```

基础安装支持 Binance、OKX、IBKR、链上钱包和手动账户。moomoo 和
Longbridge SDK 是可选依赖，只在需要时安装：

```bash
pip install "asset-mcp[moomoo]"
pip install "asset-mcp[longbridge]"
pip install "asset-mcp[moomoo,longbridge]"
```

`asset-mcp init` 不会覆盖已有配置文件，除非传入 `--force`：

```bash
asset-mcp init --force
```

本地开发时，克隆仓库并用 [`uv`](https://docs.astral.sh/uv/) 安装依赖：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # 如果尚未安装 uv
uv sync --extra dev --extra moomoo --extra longbridge
uv run asset-mcp init --path config.local.yaml
```

如果不需要 moomoo 或 Longbridge 支持，可以省略这些 optional extras：

```bash
uv sync --extra dev
```

## 配置

`asset-mcp init` 会把初始配置模板写入
`~/.config/asset-mcp/config.local.yaml`。传入 `--path <file>` 可以写入其他路径。

如果你从 PyPI 安装，`asset-mcp init` 写入的模板与仓库里的
`config.example.yaml` 相同。完整字段和内联注释请参考 GitHub 上的该文件
（见下方 **链接**）。

真实 API key 和个人资产余额只应保存在本地配置文件中，不要提交到仓库。
每个账户的 `id` 必须唯一且稳定；这个 id 会出现在 MCP 响应中，也用于过滤。

### Binance

在 Binance API 管理页面创建一个**只读** API key。保持 Withdraw、Trade、
Margin 和 Futures 权限关闭。

```yaml
exchanges:
  binance:
    accounts:
      - id: binance-main
        label: Binance Main
        enabled: true
        apiKey: "replace-with-read-only-key"
        apiSecret: "replace-with-read-only-secret"
        # environment: production    # optional
```

### OKX

创建一个只有 **Read** 权限的 OKX API key。`passphrase` 是生成 key 时你设置的口令。

```yaml
exchanges:
  okx:
    accounts:
      - id: okx-main
        label: OKX Main
        enabled: true
        apiKey: "replace-with-read-only-key"
        apiSecret: "replace-with-read-only-secret"
        passphrase: "replace-with-passphrase"
        # domain: https://www.okx.com   # optional
```

### moomoo (OpenD)

启动 `asset-mcp` 之前，需要安装并启动
[Futu/moomoo OpenD](https://openapi.futunn.com/futu-api-doc/quick/opend-base.html)
客户端，并完成登录。可选 SDK 通过 `pip install "asset-mcp[moomoo]"` 安装。

```yaml
brokers:
  moomoo:
    accounts:
      - id: moomoo-us
        label: moomoo US
        enabled: true
        host: 127.0.0.1
        port: 11111
        trdMarket: US                # US / HK / CN / SG
        securityFirm: FUTUSECURITIES # or FUTUINC / MOOMOOSG / FUTUSG
        # accountId: 12345678        # optional; only needed for multi-account setups
```

### Longbridge

创建一个带只读 scope 的 Longbridge OpenAPI 应用，并复制 App Key、App Secret 和
Access Token。可选 SDK 通过 `pip install "asset-mcp[longbridge]"` 安装。

```yaml
brokers:
  longbridge:
    accounts:
      - id: longbridge-main
        label: Longbridge Main
        enabled: true
        appKey: "replace-with-app-key"
        appSecret: "replace-with-app-secret"
        accessToken: "replace-with-access-token"
```

### IBKR

IBKR 支持基于 Flex Web Service。在 IBKR Client Portal 中启用 Flex Web Service，
创建一个输出 XML 的 Activity Flex Query，并至少包含 Cash Report 和 Open
Positions。然后在 `brokers.ibkr.accounts` 下配置生成的 token 和 query ID：

```yaml
brokers:
  ibkr:
    accounts:
      - id: ibkr-main
        label: IBKR Main
        enabled: true
        token: "replace-with-flex-web-service-token"
        queryId: "replace-with-flex-query-id"
        baseUrl: https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService
        accountId: U1234567
        version: 3
        statementRetries: 3
        statementRetryDelaySeconds: 5
```

留空 `accountId` 会导入 Flex Query 中包含的所有账户；设置它则只保留多账户报表中的
某一个账户。Flex Activity Statement 是报表数据，不是实时行情流，因此更适合做周期性
净资产快照，而不是高频轮询。

### 链上钱包

在 `onchain.accounts` 下配置公开钱包地址。provider 会发现每个地址持有的资产。
EVM 链会查询原生余额、内置主流 ERC-20 token 列表，以及该地址下显式配置的
ERC-20 合约。Solana 使用 `getTokenAccountsByOwner` 查询 SPL token 账户。
Bitcoin 和 TRON 使用公开地址 API。不支持私钥、助记词、交易、转账或授权操作。

内置支持的链：

- `bitcoin` / `btc`
- `ethereum` / `eth` / `1`
- `solana` / `sol` / `501`
- `bsc` / `bnb` / `56`
- `tron` / `trx`
- `polygon` / `matic` / `137`
- `avalanche` / `avax` / `43114`
- `arbitrum` / `42161`
- `base` / `8453`
- `optimism` / `op` / `10`

链上钱包地址配置示例：

```yaml
onchain:
  accounts:
    - id: onchain-wallet
      label: On-chain Wallet
      enabled: true
      addresses:
        - chain: bitcoin
          address: "bc1..."
        - chain: ethereum
          address: "0x..."
          tokens:
            - symbol: CUSTOM
              name: Custom ERC-20 Token
              contractAddress: "0x..."
              decimals: 18
              coinGeckoId: ""
        - chain: solana
          address: "..."
        - chain: bsc
          address: "0x..."
```

如果你希望使用自己的节点或付费 provider，而不是默认公共端点，每个地址都可以覆盖
`rpcUrl` 或 `explorerApiUrl`。原生 token 价格会先读取 `rates`，再回退到
CoinGecko。没有 Jupiter 价格的 Solana SPL token 仍会返回，但美元价值为零。

配置 ERC-20 token 时，`symbol`、`contractAddress` 和 `decimals` 是必填项。
`name` 可选。添加 `coinGeckoId` 可获取实时美元价格，也可以在 `rates` 中提供该
token 的价格；如果没有可用价格，该 token 仍会返回，但美元价值为零。如果启用了
Covalent indexer，显式配置的 ERC-20 合约会与 indexer 返回的资产一起查询，并跳过
已经由 indexer 返回的合约。

如果想要类似 Etherscan 的完整 token inventory，而不是内置主流 EVM token 列表，
可以配置可选 indexer：

```yaml
onchain:
  indexer:
    provider: covalent
    apiKey: "replace-with-covalent-api-key"
```

### 手动资产和汇率

每个手动资产的美元价值按 `quantity * rates[currency]` 计算。链上原生 token 会先读取
`rates`，再回退到 CoinGecko。

```yaml
rates:
  USD: 1.0
  CNY: 0.14
  HKD: 0.128

manual:
  accounts:
    - id: alipay
      label: Alipay
      enabled: true
      category: cash
      assets:
        - symbol: CNY
          quantity: 25000
          currency: CNY
    - id: home
      label: Primary residence
      enabled: true
      category: property
      assets:
        - symbol: USD
          quantity: 500000
          currency: USD
```

## 运行 MCP Server

```bash
asset-mcp
```

默认情况下，服务器按以下顺序读取配置：

1. `ASSET_MCP_CONFIG`
2. 当前目录下的 `config.local.yaml`
3. `~/.config/asset-mcp/config.local.yaml`

使用其他路径：

```bash
ASSET_MCP_CONFIG=/path/to/config.local.yaml asset-mcp
```

## MCP 客户端配置

使用 stdio transport。客户端配置示例：

```json
{
  "mcpServers": {
    "asset-mcp": {
      "command": "asset-mcp"
    }
  }
}
```

如果你想使用非默认配置路径，可以通过 `ASSET_MCP_CONFIG` 传入绝对路径。

## MCP 工具

- `get_net_worth`：总净资产和分组汇总。
- `get_assets`：标准化资产行，支持可选过滤条件。
- `get_asset_dashboard_data`：面向图表的分组数据。
- `health_check_sources`：按账户返回配置和连接状态。

provider 调用带有单 provider 超时隔离。查询多个 provider 时，慢速或不可用来源会被记录到
`providerErrors`，工具会返回已经可用的数据，并设置 `partial: true`。可能阻塞或向原生
stdout 输出内容的 SDK-backed provider 会运行在子进程中，因此超时请求可以被终止，不会让
MCP server 卡住，也不会破坏 stdio transport。

`providerErrors` 中包含稳定的机器可读错误码：

| code | 含义 | 可重试 |
| --- | --- | --- |
| `provider_timeout` | provider 在单 provider 超时时间内没有返回。 | 是 |
| `provider_exception` | provider 抛出异常。原始错误会被清洗。 | 否 |
| `provider_exited` | 子进程隔离的 provider 未返回结果就退出。 | 是 |

连接 MCP server 后，可以这样提问：

```text
Use asset-mcp to summarize my net worth by account and asset category.
```

要端到端验证配置，请让 MCP 客户端调用 `health_check_sources`。每个启用账户都应该返回
`ok: true`；否则通常说明配置错误或 provider 无法访问。

## 故障排查

- **`health_check_sources` 对每个账户都返回 `configured: false`。**
  确认配置文件位于三个解析位置之一：`ASSET_MCP_CONFIG`、当前目录，或
  `~/.config/asset-mcp/config.local.yaml`，并确认每个账户都有 `enabled: true`。
- **moomoo 账户返回 `provider_exited` 或 `provider_timeout`。** OpenD 没有运行、
  没有登录，或端口被阻塞。用 `nc -z 127.0.0.1 11111` 验证 daemon，并确认安装了
  SDK extras：`pip install "asset-mcp[moomoo]"`。
- **响应包含 `partial: true` 和 `providerErrors` 数组。** 一个或多个 provider 失败。
  `provider_timeout` 可以安全重试；`provider_exception` 通常表示凭据过期或错误；
  `provider_exited` 表示子进程隔离的 provider 崩溃，常见于 moomoo/Longbridge SDK 问题。
- **MCP 客户端连接后立即显示 "Transport closed"。** 某个 provider 可能向 stdout 写入
  banner 或 warning，破坏了 JSON-RPC stream。可以在终端运行
  `ASSET_MCP_CONFIG=config.local.yaml asset-mcp`，检查第一条 JSON frame 之前是否有
  异常输出。
- **链上地址明明持有 token，却显示零余额。** 确认 `chain` 值匹配受支持的别名，并确认
  自定义 ERC-20 条目包含 `symbol`、`contractAddress` 和 `decimals` 三个字段。

## 安全说明

- 对交易所使用只读 API key。
- 不要提交 `config.local.yaml`。
- 不要给 API key 开启提现、转账或交易权限。
- 尽可能使用带只读权限的 Longbridge API key 凭据。
- IBKR Flex Web Service 只用于只读报表查询。
- 银行和支付宝余额只支持手动录入；本项目不会抓取或自动化这些服务。
- 链上钱包支持只基于地址，只读。不要在配置中填写私钥或助记词。

## 链接

- 源码： https://github.com/cidzhao/asset-mcp
- Issues： https://github.com/cidzhao/asset-mcp/issues
- PyPI： https://pypi.org/project/asset-mcp/

---

## 贡献者说明

### 代码结构

- `src/asset_mcp/server.py`：MCP stdio 入口和工具定义。
- `src/asset_mcp/service.py`：应用服务编排层。
- `src/asset_mcp/domain/`：标准化模型、聚合和过滤逻辑。
- `src/asset_mcp/config/`：配置模型、YAML 解析、校验和 secret 脱敏。
- `src/asset_mcp/providers/registry.py`：source 到 provider factory 的注册表。
- `src/asset_mcp/providers/exchanges/`：交易所 provider，目前包括 Binance 和 OKX。
- `src/asset_mcp/providers/brokerages/`：券商 provider，目前包括 moomoo、Longbridge 和 IBKR。
- `src/asset_mcp/providers/onchain/`：链上钱包 provider 和链相关包边界。
- `src/asset_mcp/providers/manual/`：手动配置资产 provider。
- `tests/config/`、`tests/domain/` 和 `tests/providers/`：与源码结构匹配的回归测试。

兼容性 re-export 模块会保留旧导入路径，例如 `asset_mcp.models`、
`asset_mcp.aggregation` 和 `asset_mcp.providers.binance`。新代码应优先使用上面的包路径。

### 开发

运行测试前安装开发依赖：

```bash
uv sync --extra dev
```

回归测试使用 fake provider client 和内联样例配置，不需要 `config.local.yaml`、真实 API key、
运行中的 OpenD、券商 SDK session 或外网访问。

运行测试：

```bash
uv run pytest
```

运行 Python 编译语法检查：

```bash
uv run python -m compileall src tests
```

用示例配置在本地运行 server：

```bash
ASSET_MCP_CONFIG=config.example.yaml uv run asset-mcp
```

构建本地包产物：

```bash
uv build
```

这会把 wheel 和 source distribution 写入 `dist/`。

### 发布检查清单

- 同时更新 `pyproject.toml` 中的包版本，以及 `src/asset_mcp/__init__.py` 中 fallback
  `__version__` 的值。
- 运行 `uv run python -m compileall src tests` 和 `uv run pytest`。
- 运行 `uv build`，发布前检查 source distribution 中没有本地专用文件。
- 从 GitHub release 发布，让 PyPI workflow 构建、测试并上传最终产物。

### 添加 Provider

- 加密货币交易所放在 `src/asset_mcp/providers/exchanges/<platform>/` 下。
- 券商集成放在 `src/asset_mcp/providers/brokerages/<platform>/` 下。
- 手动资产或链上逻辑放在现有 provider package 下。
- 在 `src/asset_mcp/providers/registry.py` 中注册新的 source。
- 如果 provider 需要新的 YAML 字段，扩展 `src/asset_mcp/config/` 下的配置模型和解析逻辑。
- 在 `tests/providers/` 下添加 provider 回归测试。
- 除非有意变更公开 contract 并同步更新测试和文档，否则保持现有 MCP 响应结构和 source 名称。

### Provider stdout hygiene

MCP server 使用 stdio transport，因此 `stdout` 专用于 JSON-RPC protocol frame。任何写入
`stdout` 的 banner、warning、权限表、进度行或原生 SDK log，都可能破坏 MCP stream，
并在客户端表现为 `Transport closed`。

添加新的券商或交易所 provider 时：

- 用 `asset_mcp.providers.stdio.redirect_sdk_stdout()` 包住所有第三方 SDK 调用。
- 假设 SDK 可能绕过 `print()`，从原生代码或后台线程直接写入 file descriptor 1；
  单独使用 `contextlib.redirect_stdout()` 不够。
- 覆盖每一条网络/API 路径，不只测 health check。quote/market-data endpoint 即使在
  account-balance endpoint 安静时，也可能输出权限表。
- 添加使用 `capfd` 和 `os.write(1, ...)` 的回归测试，证明 provider 调用后 `stdout`
  为空。
