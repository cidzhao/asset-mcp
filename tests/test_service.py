from __future__ import annotations

import time

import pytest

import asset_mcp.service as service_module
from asset_mcp.config import AppConfig
from asset_mcp.domain.models import AccountStatus, Asset
from asset_mcp.service import AssetService


@pytest.mark.asyncio
async def test_net_worth_returns_partial_result_when_provider_times_out(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "build_provider_entries",
        lambda config, source=None: [
            ("manual", _FastProvider()),
            ("ibkr", _BlockingProvider()),
        ],
    )

    service = AssetService(AppConfig(), provider_timeout_seconds=0.01)
    started = time.monotonic()

    result = await service.get_net_worth()

    assert time.monotonic() - started < 0.15
    assert result["ok"] is False
    assert result["partial"] is True
    assert result["totalValueUsd"] == 100
    assert result["assetCount"] == 1
    assert result["providerErrors"] == [
        {
            "source": "ibkr",
            "code": "provider_timeout",
            "error": "Timeout",
            "message": "fetch_assets timed out after 0.01s",
            "retryable": True,
        }
    ]


@pytest.mark.asyncio
async def test_health_check_returns_partial_result_when_provider_times_out(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "build_provider_entries",
        lambda config, source=None: [
            ("manual", _FastProvider()),
            ("ibkr", _BlockingProvider()),
        ],
    )

    service = AssetService(AppConfig(), provider_timeout_seconds=0.01)

    result = await service.health_check_sources()

    assert result["ok"] is False
    assert result["partial"] is True
    assert result["accounts"] == [
        {
            "source": "manual",
            "accountId": "manual-main",
            "accountLabel": "Manual",
            "enabled": True,
            "ok": True,
            "message": "ok",
        }
    ]
    assert result["providerErrors"][0]["source"] == "ibkr"
    assert result["providerErrors"][0]["code"] == "provider_timeout"
    assert result["providerErrors"][0]["error"] == "Timeout"
    assert result["providerErrors"][0]["retryable"] is True


@pytest.mark.asyncio
async def test_assets_payload_includes_partial_metadata(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "build_provider_entries",
        lambda config, source=None: [
            ("manual", _FastProvider()),
            ("ibkr", _BlockingProvider()),
        ],
    )

    service = AssetService(AppConfig(), provider_timeout_seconds=0.01)

    result = await service.get_assets_payload()

    assert result["ok"] is False
    assert result["partial"] is True
    assert result["count"] == 1
    assert result["assets"][0]["accountId"] == "manual-main"
    assert result["providerErrors"][0]["source"] == "ibkr"
    assert result["providerErrors"][0]["code"] == "provider_timeout"


class _FastProvider:
    async def fetch_assets(self) -> list[Asset]:
        return [
            Asset(
                source="manual",
                accountId="manual-main",
                accountLabel="Manual",
                category="cash",
                symbol="USD",
                quantity=100,
                currency="USD",
                unitPriceUsd=1,
                valueUsd=100,
                updatedAt="2026-05-31T00:00:00Z",
            )
        ]

    async def health_check(self) -> list[AccountStatus]:
        return [AccountStatus("manual", "manual-main", "Manual", True, True, "ok")]


class _BlockingProvider:
    async def fetch_assets(self) -> list[Asset]:
        time.sleep(0.2)
        return []

    async def health_check(self) -> list[AccountStatus]:
        time.sleep(0.2)
        return []
