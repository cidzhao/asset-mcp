from asset_mcp.domain.aggregation import build_dashboard_data, build_net_worth, filter_assets
from asset_mcp.domain.models import Asset


def test_aggregation_groups_by_category_source_account_and_currency():
    assets = [
        _asset("binance", "binance-main", "crypto", "BTC", 1000, wallet="spot"),
        _asset("manual", "bank-cmb", "cash", "USD", 200),
        _asset("manual", "alipay-main", "cash", "CNY", 100),
    ]

    result = build_net_worth(assets)

    assert result["totalValueUsd"] == 1300
    assert result["byCategory"][0]["key"] == "crypto"
    assert result["bySource"][0]["key"] == "binance"
    assert {row["accountId"] for row in result["byAccount"]} == {
        "binance-main",
        "bank-cmb",
        "alipay-main",
    }
    assert {row["key"] for row in result["byCurrency"]} == {"BTC", "USD", "CNY"}
    assert result["byWallet"][0]["key"] == "spot"


def test_dashboard_data_is_chart_ready():
    dashboard = build_dashboard_data(
        [
            _asset("binance", "binance-main", "crypto", "BTC", 1000),
            _asset("manual", "bank-cmb", "cash", "USD", 200),
        ]
    )

    assert dashboard["totalValueUsd"] == 1200
    assert dashboard["pieByCategory"][0]["label"] == "crypto"
    assert dashboard["topAssets"][0]["symbol"] == "BTC"


def test_filter_assets_by_source_account_and_category():
    assets = [
        _asset("binance", "binance-main", "crypto", "BTC", 1000),
        _asset("manual", "bank-cmb", "cash", "USD", 200),
    ]

    filtered = filter_assets(assets, source="manual", accountId="bank-cmb", category="cash")

    assert len(filtered) == 1
    assert filtered[0].symbol == "USD"


def _asset(source, account_id, category, symbol, value, wallet=None):
    return Asset(
        source=source,
        accountId=account_id,
        accountLabel=account_id,
        category=category,
        symbol=symbol,
        quantity=1,
        currency=symbol,
        unitPriceUsd=value,
        valueUsd=value,
        updatedAt="2026-05-08T00:00:00Z",
        wallet=wallet,
    )
