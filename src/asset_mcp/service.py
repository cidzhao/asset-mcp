from __future__ import annotations

import asyncio
import multiprocessing as mp
import os
import queue
from dataclasses import dataclass
from enum import Enum
from typing import Any

from asset_mcp.domain.aggregation import build_dashboard_data, build_net_worth, filter_assets
from asset_mcp.config import AppConfig, load_config
from asset_mcp.domain.models import AccountStatus, Asset
from asset_mcp.providers.base import AssetProvider
from asset_mcp.providers.registry import PROVIDER_FACTORIES, build_provider_entries

DEFAULT_PROVIDER_TIMEOUT_SECONDS = 20.0
PROCESS_ISOLATED_SOURCES = {"longbridge", "moomoo"}


class ProviderErrorCode(str, Enum):
    TIMEOUT = "provider_timeout"
    PROVIDER_EXCEPTION = "provider_exception"
    PROVIDER_EXITED = "provider_exited"


@dataclass(frozen=True)
class _ProviderError:
    source: str
    code: ProviderErrorCode
    error: str
    message: str
    retryable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "code": self.code.value,
            "error": self.error,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class _FetchAssetsResult:
    assets: list[Asset]
    provider_errors: list[_ProviderError]

    @property
    def partial(self) -> bool:
        return bool(self.provider_errors)


@dataclass(frozen=True)
class _ProviderActionResult:
    source: str
    items: list[Any]
    error: _ProviderError | None = None


class AssetService:
    def __init__(
        self,
        config: AppConfig | None = None,
        provider_timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    ):
        self.config = config
        self.provider_timeout_seconds = provider_timeout_seconds

    async def get_assets(
        self,
        source: str | None = None,
        accountId: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        result = await self._fetch_assets_result(source=source)
        if result.provider_errors:
            _raise_provider_errors(result.provider_errors)
        assets = filter_assets(result.assets, source, accountId, category)
        return [asset.to_dict() for asset in assets]

    async def get_assets_payload(
        self,
        source: str | None = None,
        accountId: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        result = await self._fetch_assets_result(source=source)
        assets = filter_assets(result.assets, source, accountId, category)
        payload: dict[str, Any] = {
            "assets": [asset.to_dict() for asset in assets],
            "count": len(assets),
        }
        return _with_fetch_status(payload, result)

    async def get_net_worth(self) -> dict[str, Any]:
        result = await self._fetch_assets_result()
        return _with_fetch_status(build_net_worth(result.assets), result)

    async def get_asset_dashboard_data(self) -> dict[str, Any]:
        result = await self._fetch_assets_result()
        return _with_fetch_status(build_dashboard_data(result.assets), result)

    async def health_check_sources(self) -> dict[str, Any]:
        config = self._config()
        results = await asyncio.gather(
            *[
                self._run_provider_action(provider_source, provider, config, "health_check")
                for provider_source, provider in build_provider_entries(config)
            ],
        )
        rows: list[AccountStatus] = []
        provider_errors: list[_ProviderError] = []
        for result in results:
            if result.error is not None:
                provider_errors.append(result.error)
            else:
                rows.extend(result.items)
        provider_error_dicts = [error.to_dict() for error in provider_errors]
        return {
            "ok": all(row.ok for row in rows) and not provider_errors,
            "partial": bool(provider_errors),
            "accounts": [row.to_dict() for row in rows],
            "providerErrors": provider_error_dicts,
        }

    async def _fetch_all_assets(self, source: str | None = None) -> list[Asset]:
        result = await self._fetch_assets_result(source=source)
        if result.provider_errors:
            _raise_provider_errors(result.provider_errors)
        return result.assets

    async def _fetch_assets_result(self, source: str | None = None) -> _FetchAssetsResult:
        config = self._config()
        results = await asyncio.gather(
            *[
                self._run_provider_action(provider_source, provider, config, "fetch_assets")
                for provider_source, provider in build_provider_entries(config, source=source)
            ],
        )
        assets: list[Asset] = []
        provider_errors: list[_ProviderError] = []
        for result in results:
            if result.error is not None:
                provider_errors.append(result.error)
            else:
                assets.extend(result.items)
        return _FetchAssetsResult(assets=assets, provider_errors=provider_errors)

    async def _run_provider_action(
        self,
        source: str,
        provider: AssetProvider,
        config: AppConfig,
        action: str,
    ) -> _ProviderActionResult:
        if source in PROCESS_ISOLATED_SOURCES:
            return await asyncio.to_thread(
                _run_provider_action_in_process,
                source,
                config,
                action,
                self.provider_timeout_seconds,
            )
        return await _run_provider_action_in_thread(
            source,
            provider,
            action,
            self.provider_timeout_seconds,
        )

    def _config(self) -> AppConfig:
        return self.config if self.config is not None else load_config()


async def _run_provider_action_in_thread(
    source: str,
    provider: AssetProvider,
    action: str,
    timeout_seconds: float,
) -> _ProviderActionResult:
    try:
        items = await asyncio.wait_for(
            asyncio.to_thread(_run_provider_action_sync, provider, action),
            timeout=timeout_seconds,
        )
        return _ProviderActionResult(source=source, items=items)
    except asyncio.TimeoutError:
        return _ProviderActionResult(
            source=source,
            items=[],
            error=_timeout_error(source, action, timeout_seconds),
        )
    except Exception as exc:  # noqa: BLE001
        return _ProviderActionResult(source=source, items=[], error=_provider_error(source, exc))


def _run_provider_action_sync(provider: AssetProvider, action: str) -> list[Any]:
    return asyncio.run(getattr(provider, action)())


def _run_provider_action_in_process(
    source: str,
    config: AppConfig,
    action: str,
    timeout_seconds: float,
) -> _ProviderActionResult:
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue(maxsize=1)
    process = ctx.Process(
        target=_provider_action_child,
        args=(source, config, action, result_queue),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        return _ProviderActionResult(
            source=source,
            items=[],
            error=_timeout_error(source, action, timeout_seconds),
        )

    try:
        payload = result_queue.get(timeout=1)
    except queue.Empty:
        error = _ProviderError(
            source=source,
            code=ProviderErrorCode.PROVIDER_EXITED,
            error="ProviderExited",
            message="provider exited without returning a result",
            retryable=True,
        )
        return _ProviderActionResult(source=source, items=[], error=error)

    if not payload["ok"]:
        error = _ProviderError(
            source=source,
            code=ProviderErrorCode.PROVIDER_EXCEPTION,
            error=payload["error"],
            message=payload["message"],
            retryable=False,
        )
        return _ProviderActionResult(source=source, items=[], error=error)

    item_cls = Asset if action == "fetch_assets" else AccountStatus
    return _ProviderActionResult(
        source=source,
        items=[item_cls(**item) for item in payload["items"]],
    )


def _provider_action_child(
    source: str,
    config: AppConfig,
    action: str,
    result_queue: Any,
) -> None:
    _redirect_stdio_to_devnull()
    try:
        provider = PROVIDER_FACTORIES[source](config)
        items = asyncio.run(getattr(provider, action)())
        result_queue.put({"ok": True, "items": [item.to_dict() for item in items]})
    except Exception as exc:  # noqa: BLE001
        result_queue.put(
            {
                "ok": False,
                "error": exc.__class__.__name__,
                "message": exc.__class__.__name__,
            }
        )


def _redirect_stdio_to_devnull() -> None:
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
    finally:
        os.close(devnull)


def _timeout_error(source: str, action: str, timeout_seconds: float) -> _ProviderError:
    return _ProviderError(
        source=source,
        code=ProviderErrorCode.TIMEOUT,
        error="Timeout",
        message=f"{action} timed out after {timeout_seconds:g}s",
        retryable=True,
    )


def _provider_error(source: str, exc: Exception) -> _ProviderError:
    return _ProviderError(
        source=source,
        code=ProviderErrorCode.PROVIDER_EXCEPTION,
        error=exc.__class__.__name__,
        message=exc.__class__.__name__,
        retryable=False,
    )


def _raise_provider_errors(errors: list[_ProviderError]) -> None:
    names = ", ".join(f"{error.source}:{error.error}" for error in errors)
    raise RuntimeError(f"Failed to fetch one or more providers: {names}")


def _with_fetch_status(payload: dict[str, Any], result: _FetchAssetsResult) -> dict[str, Any]:
    payload["ok"] = not result.provider_errors
    payload["partial"] = result.partial
    payload["providerErrors"] = [error.to_dict() for error in result.provider_errors]
    return payload
