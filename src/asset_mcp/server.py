from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from asset_mcp.config import ConfigError
from asset_mcp.service import AssetService

mcp = FastMCP(
    "asset-mcp",
    instructions=(
        "Read-only personal asset aggregation server. It summarizes configured "
        "Binance, OKX, moomoo OpenD, Longbridge, IBKR, and manual accounts in USD."
    ),
)


@mcp.tool()
async def get_net_worth() -> dict[str, Any]:
    """Return total net worth and summaries by category, source, account, and currency."""
    return await _call_service("get_net_worth")


@mcp.tool()
async def get_assets(
    source: str | None = None,
    accountId: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Return normalized assets, optionally filtered by source, accountId, or category."""
    service = AssetService()
    try:
        assets = await service.get_assets(source=source, accountId=accountId, category=category)
        return {"assets": assets, "count": len(assets)}
    except ConfigError as exc:
        return {"ok": False, "error": exc.__class__.__name__, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": exc.__class__.__name__, "message": exc.__class__.__name__}


@mcp.tool()
async def get_asset_dashboard_data() -> dict[str, Any]:
    """Return chart-ready data for asset dashboards."""
    return await _call_service("get_asset_dashboard_data")


@mcp.tool()
async def health_check_sources() -> dict[str, Any]:
    """Check configured sources and accounts without returning secrets."""
    return await _call_service("health_check_sources")


async def _call_service(method_name: str, **kwargs) -> dict[str, Any] | list[dict[str, Any]]:
    service = AssetService()
    try:
        method = getattr(service, method_name)
        return await method(**kwargs)
    except ConfigError as exc:
        return {"ok": False, "error": exc.__class__.__name__, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": exc.__class__.__name__, "message": exc.__class__.__name__}


def main() -> None:
    mcp.run()
