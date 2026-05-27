import pytest

from asset_mcp.config import parse_config
from asset_mcp.providers.manual import ManualProvider


@pytest.mark.asyncio
async def test_manual_provider_converts_assets_with_configured_rates():
    config = parse_config(
        {
            "rates": {"USD": 1, "CNY": 0.14},
            "manual": {
                "accounts": [
                    {
                        "id": "alipay-main",
                        "label": "Alipay",
                        "category": "cash",
                        "assets": [{"symbol": "CNY", "quantity": 1000, "currency": "CNY"}],
                    },
                    {
                        "id": "property-home",
                        "label": "Property",
                        "category": "manual",
                        "assets": [
                            {
                                "symbol": "HOME",
                                "quantity": 1,
                                "currency": "CNY",
                                "unitPriceUsd": 200000,
                            }
                        ],
                    },
                    {
                        "id": "disabled",
                        "label": "Disabled",
                        "enabled": False,
                        "category": "cash",
                        "assets": [{"symbol": "USD", "quantity": 999, "currency": "USD"}],
                    },
                ]
            },
        }
    )

    assets = await ManualProvider(config).fetch_assets()

    assert len(assets) == 2
    assert assets[0].accountId == "alipay-main"
    assert assets[0].valueUsd == 140
    assert assets[1].accountId == "property-home"
    assert assets[1].valueUsd == 200000


@pytest.mark.asyncio
async def test_manual_health_check_reports_missing_rates():
    config = parse_config(
        {
            "manual": {
                "accounts": [
                    {
                        "id": "bank",
                        "label": "Bank",
                        "category": "cash",
                        "assets": [{"symbol": "SGD", "quantity": 1, "currency": "SGD"}],
                    }
                ]
            }
        }
    )

    statuses = await ManualProvider(config).health_check()

    assert statuses[0].ok is False
    assert "missing rates" in statuses[0].message
