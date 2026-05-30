from __future__ import annotations

from typing import Any


SECRET_KEYS = {
    "apikey",
    "apisecret",
    "appkey",
    "appsecret",
    "accesstoken",
    "clientsecret",
    "passphrase",
    "secret",
    "token",
    "password",
}


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***REDACTED***" if str(key).lower() in SECRET_KEYS else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value
