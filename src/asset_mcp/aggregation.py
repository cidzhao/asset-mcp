from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from asset_mcp.models import Asset, sum_value_usd


def filter_assets(
    assets: Iterable[Asset],
    source: str | None = None,
    accountId: str | None = None,
    category: str | None = None,
) -> list[Asset]:
    return [
        asset
        for asset in assets
        if (source is None or asset.source == source)
        and (accountId is None or asset.accountId == accountId)
        and (category is None or asset.category == category)
    ]


def build_net_worth(assets: list[Asset]) -> dict[str, Any]:
    return {
        "baseCurrency": "USD",
        "totalValueUsd": sum_value_usd(assets),
        "byCategory": _group(assets, lambda asset: asset.category),
        "bySource": _group(assets, lambda asset: asset.source),
        "byWallet": _group(assets, lambda asset: asset.wallet or asset.source),
        "byAccount": _group(
            assets,
            lambda asset: asset.accountId,
            lambda asset: {
                "accountId": asset.accountId,
                "accountLabel": asset.accountLabel,
                "source": asset.source,
            },
        ),
        "byCurrency": _group(assets, lambda asset: asset.currency),
        "assetCount": len(assets),
    }


def build_dashboard_data(assets: list[Asset]) -> dict[str, Any]:
    by_category = build_net_worth(assets)["byCategory"]
    by_source = build_net_worth(assets)["bySource"]
    by_wallet = build_net_worth(assets)["byWallet"]
    by_account = build_net_worth(assets)["byAccount"]
    top_assets = sorted(
        [
            {
                "label": asset.name or asset.symbol,
                "symbol": asset.symbol,
                "source": asset.source,
                "accountId": asset.accountId,
                "valueUsd": round(asset.valueUsd, 8),
            }
            for asset in assets
        ],
        key=lambda item: item["valueUsd"],
        reverse=True,
    )
    return {
        "baseCurrency": "USD",
        "totalValueUsd": sum_value_usd(assets),
        "pieByCategory": _chart_rows(by_category, "category"),
        "pieBySource": _chart_rows(by_source, "source"),
        "pieByWallet": _chart_rows(by_wallet, "wallet"),
        "barByAccount": _chart_rows(by_account, "accountId"),
        "topAssets": top_assets[:20],
    }


def _group(
    assets: list[Asset],
    key_fn,
    meta_fn=None,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    quantities: dict[str, float] = defaultdict(float)
    for asset in assets:
        key = str(key_fn(asset))
        if key not in buckets:
            buckets[key] = {"key": key, "valueUsd": 0.0, "assetCount": 0}
            if meta_fn is not None:
                buckets[key].update(meta_fn(asset))
        buckets[key]["valueUsd"] += asset.valueUsd
        buckets[key]["assetCount"] += 1
        quantities[key] += asset.quantity

    rows = []
    for key, row in buckets.items():
        row["valueUsd"] = round(row["valueUsd"], 8)
        rows.append(row)
    return sorted(rows, key=lambda row: row["valueUsd"], reverse=True)


def _chart_rows(rows: list[dict[str, Any]], label_key: str) -> list[dict[str, Any]]:
    return [
        {
            "label": row.get(label_key) or row["key"],
            "valueUsd": row["valueUsd"],
            "assetCount": row["assetCount"],
        }
        for row in rows
    ]
